"""
Islamic Guidance AI - Main FastAPI Backend Application (OPTIMIZED v2.1)
Provides AI-powered Islamic guidance using Gemini AI and external Islamic text APIs
"""

import os
import sys
import json
import traceback
import uuid
import time

try:
    from dotenv import load_dotenv
except ImportError as ex:
    print(f"[ERROR] Missing dependencies. Please install requirements.txt: {ex}", file=sys.stderr)
    sys.exit(1)


try:
    import uvicorn
    import asyncio
    import hashlib
    from fastapi import FastAPI, HTTPException
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi import Request
    from pydantic import BaseModel
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    import google.generativeai as genai
    from typing import Optional, List, Dict
	from backend.vector_search import search_semantic_async
    print("[IMPORT] Core dependencies loaded successfully", file=sys.stdout, flush=True)
except ImportError as ex:
    print(f"[CRITICAL] Failed to import core dependencies: {ex}", file=sys.stderr, flush=True)
    print(f"[CRITICAL] Stack trace: {traceback.format_exc()}", file=sys.stderr, flush=True)
    raise

# Import serverless detection utility
try:
    from .utils import detect_serverless_environment
except Exception:
    try:
        from utils import detect_serverless_environment
    except Exception:
        import importlib
        detect_serverless_environment = importlib.import_module("utils").detect_serverless_environment

# Import example prompts
try:
    from .utils import EXAMPLE_PROMPTS
except Exception:
    try:
        from utils import EXAMPLE_PROMPTS
    except Exception:
        import importlib
        EXAMPLE_PROMPTS = importlib.import_module("utils").EXAMPLE_PROMPTS

# Import available Gemini models
try:
    from .utils import GEMINI_MODELS
except Exception:
    try:
        from utils import GEMINI_MODELS
    except Exception:
        import importlib
        GEMINI_MODELS = importlib.import_module("utils").GEMINI_MODELS

# =============================================================================
# MODULE-LEVEL CONFIGURATION
# =============================================================================

# Load environment variables
load_dotenv()

# Environment Configuration - More robust detection
# Check if we're actually in Vercel (not just local with VERCEL_ENV set)
IS_SERVERLESS = bool(
    os.getenv("VERCEL") == "1" or 
    os.getenv("AWS_LAMBDA_FUNCTION_NAME") or 
    os.getenv("AWS_EXECUTION_ENV") or
    (os.getenv("VERCEL_ENV") and os.getenv("VERCEL_ENV") != "development")
)
API_KEY = os.getenv("GEMINI_API_KEY")

# Cache models and extractors at module level (Issue #16 - P2)
_cached_model = None
_yake_extractor = None
_custom_extractor = None

# =============================================================================
# IMPORT STRATEGY - Simplified (Issue #23 - P3)
# =============================================================================

# Add project root to sys.path to fix imports in local dev
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import services with fail-fast approach
try:
    # Try absolute import first (Vercel/Production)
    from backend.services import search_quran_async, search_hadith_async
except ImportError:
    try:
        # Try relative import (Local development)
        from services import search_quran_async, search_hadith_async
    except ImportError as e:
        # FAIL FAST - Don't use dummy functions (Issue #9 - P1)
        print(f"[CRITICAL] Could not import services: {e}", file=sys.stderr)
        raise ImportError(f"Failed to import required services module: {e}")

# Import cache service
try:
    from backend.cache import cache
except ImportError:
    try:
        from cache import cache
    except ImportError:
        # Mock cache for environments without Vercel KV
        class MockCache:
            async def get(self, k): return None
            async def set(self, k, v, t=0): pass
            async def connect(self): pass
            async def close(self): pass
            async def ping(self): return True
            async def delete(self, k): pass
            async def clear_pattern(self, p): pass
        cache = MockCache()

# =============================================================================
# KEYWORD EXTRACTION LIBRARIES - YAKE + CUSTOM FALLBACK (Issue #4 - P0)
# =============================================================================

# Try to import YAKE (primary method)
try:
    import yake
    YAKE_AVAILABLE = True
    print("[SUCCESS] YAKE keyword extractor loaded", file=sys.stdout, flush=True)
except ImportError as e:
    YAKE_AVAILABLE = False
    print(f"[WARNING] YAKE not available: {e}. Using custom fallback", file=sys.stderr, flush=True)

# Import custom keyword extractor (fallback when YAKE unavailable)
try:
    from backend.keyword_extractor import KeywordExtractorNoDeps
except ImportError:
    try:
        from keyword_extractor import KeywordExtractorNoDeps
    except ImportError as e:
        print(f"[WARNING] Custom keyword extractor not available: {e}", file=sys.stderr, flush=True)
        KeywordExtractorNoDeps = None


# Update the Pydantic model
class GuidanceRequest(BaseModel):
    query: str
    source: str = "both"
    hadith_collection: List[str] = []
    use_semantic: bool = True  # NEW: Enable semantic search by default

# =============================================================================
# VERCEL KV-BASED RATE LIMITER (Issue #5 - P0)
# =============================================================================

class VercelKVRateLimiter:
    """
    Rate limiter using Vercel KV storage instead of in-memory storage.
    Persists across serverless invocations.
    """
    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    async def check_rate_limit(self, client_id: str) -> bool:
        """
        Check if client has exceeded rate limit.
        
        Args:
            client_id: Unique identifier (IP address)
        
        Returns:
            True if allowed, False if rate limited
        """
        key = f"ratelimit:{client_id}"
        
        try:
            count_str = await cache.get(key)
            count = int(count_str) if count_str else 0
            
            if count >= self.max_requests:
                print(f"[RATE LIMIT] Client {client_id} exceeded limit ({count}/{self.max_requests})", 
                      file=sys.stderr, flush=True)
                return False
            
            # Increment counter
            await cache.set(key, str(count + 1), ttl=self.window_seconds)
            return True
            
        except Exception as e:
            print(f"[RATE LIMIT] Error checking limit: {e}", file=sys.stderr, flush=True)
            # Fail open - allow request if rate limiter fails
            return True

# =============================================================================
# KEYWORD EXTRACTOR INITIALIZATION (Issue #16 - P2)
# =============================================================================

def get_yake_extractor():
    """
    Get cached YAKE keyword extractor instance.
    
    Returns:
        YAKE KeywordExtractor or None if unavailable
    """
    global _yake_extractor
    
    if not YAKE_AVAILABLE:
        return None
    
    if _yake_extractor is not None:
        return _yake_extractor
    
    try:
        # YAKE Configuration for optimal Islamic text keyword extraction
        _yake_extractor = yake.KeywordExtractor(
            lan="en",
            n=3,  # Max 3-word phrases
            dedupLim=0.3,
            dedupFunc='seqm',
            windowsSize=1,
            top=5  # Extract top 5, we'll take best 3
        )
        print("[SUCCESS] YAKE extractor initialized and cached", file=sys.stdout, flush=True)
        return _yake_extractor
    except Exception as e:
        print(f"[ERROR] Failed to initialize YAKE: {e}", file=sys.stderr, flush=True)
        return None

def get_custom_extractor():
    """
    Get cached custom keyword extractor instance (fallback when YAKE unavailable).
    
    Returns:
        KeywordExtractorNoDeps instance or None
    """
    global _custom_extractor
    
    if KeywordExtractorNoDeps is None:
        return None
    
    if _custom_extractor is not None:
        return _custom_extractor
    
    try:
        _custom_extractor = KeywordExtractorNoDeps(
            min_word_length=3,
            max_keywords=3
        )
        print("[SUCCESS] Custom keyword extractor initialized and cached", file=sys.stdout, flush=True)
        return _custom_extractor
    except Exception as e:
        print(f"[ERROR] Failed to initialize custom extractor: {e}", file=sys.stderr, flush=True)
        return None

# =============================================================================
# KEYWORD EXTRACTION FUNCTIONS (Issue #4 - P0)
# =============================================================================

def extract_keywords_yake(query: str, max_keywords: int = 3) -> List[str]:
    """
    Extract keywords using YAKE (fast, lightweight, no API calls).
    
    Args:
        query: User query string
        max_keywords: Maximum number of keywords to return
    
    Returns:
        List of extracted keywords
    """
    extractor = get_yake_extractor()
    
    if not extractor:
        # Fallback to custom extractor
        return extract_keywords_custom(query, max_keywords)
    
    try:
        # Extract keywords using YAKE
        yake_results = extractor.extract_keywords(query)
        
        # YAKE returns tuples: (keyword, score) where lower score = better
        sorted_keywords = sorted(yake_results, key=lambda x: x[1])[:max_keywords]
        
        # Extract just the keyword text
        keywords = [kw[0] for kw in sorted_keywords]
        
        # Clean up keywords (remove single characters, numbers only)
        cleaned_keywords = []
        for kw in keywords:
            if kw.strip() and len(kw.strip()) > 1 and not kw.strip().isdigit():
                cleaned_keywords.append(kw.strip())
        
        # Ensure we have at least 1 keyword
        if not cleaned_keywords:
            return extract_keywords_custom(query, max_keywords)
        
        print(f"[KEYWORDS] YAKE extraction: {cleaned_keywords}", file=sys.stdout, flush=True)
        return cleaned_keywords[:max_keywords]
        
    except Exception as e:
        print(f"[KEYWORDS] YAKE error: {e}, using custom fallback", file=sys.stderr, flush=True)
        return extract_keywords_custom(query, max_keywords)

def extract_keywords_custom(query: str, max_keywords: int = 3) -> List[str]:
    """
    Extract keywords using custom extractor (no external dependencies).
    
    Fallback method when YAKE is unavailable or fails.
    Features domain-specific intelligence for Islamic guidance queries.
    
    Args:
        query: User query string
        max_keywords: Maximum number of keywords to return
    
    Returns:
        List of extracted keywords
    """
    extractor = get_custom_extractor()
    
    if not extractor:
        # Final fallback: return first meaningful words
        print(f"[KEYWORDS] No extractors available, using emergency fallback", file=sys.stderr, flush=True)
        words = [w.lower().strip('.,!?;:') for w in query.split()]
        return [w for w in words if len(w) > 3][:max_keywords]
    
    try:
        keywords = extractor.extract(query, top_k=max_keywords)
        print(f"[KEYWORDS] Custom extraction: {keywords}", file=sys.stdout, flush=True)
        return keywords
    except Exception as e:
        print(f"[KEYWORDS] Custom extractor error: {e}", file=sys.stderr, flush=True)
        # Emergency fallback
        words = [w.lower().strip('.,!?;:') for w in query.split()]
        return [w for w in words if len(w) > 3][:max_keywords]

async def extract_keywords_with_cache(query: str, model, use_gemini: bool = False) -> List[str]:
    """
    Extract keywords using YAKE (primary) with custom fallback and caching.
    
    Strategy Priority:
    1. Check Vercel KV cache (fastest)
    2. Use YAKE extraction (fast, no API calls)
    3. Use custom extractor (domain-aware fallback)
    4. Optionally use Gemini if use_gemini=True (slow, uses quota)
    5. Emergency: return first meaningful words
    
    Args:
        query: User query string
        model: Gemini AI model instance
        use_gemini: If True, prefer Gemini over YAKE (default: False)
    
    Returns:
        List of extracted keywords (max 3)
    """
    # Create cache key from query hash
    query_hash = hashlib.md5(query.encode()).hexdigest()
    cache_key = f"keywords:{query_hash}"
    
    # Check cache first (Issue #4 - P0)
    try:
        cached_keywords = await cache.get(cache_key)
        if cached_keywords:
            print(f"[CACHE] Hit for keywords: '{query[:30]}...'", file=sys.stdout, flush=True)
            return json.loads(cached_keywords) if isinstance(cached_keywords, str) else cached_keywords
    except Exception as e:
        print(f"[CACHE] Error reading keywords cache: {e}", file=sys.stderr, flush=True)
    
    # Primary method: YAKE (fast, reliable, no API quota usage)
    if not use_gemini:
        try:
            keywords = extract_keywords_yake(query, max_keywords=3)
            
            # Cache successful extraction (1 hour TTL)
            await cache.set(cache_key, json.dumps(keywords), ttl=3600)
            
            return keywords
            
        except Exception as e:
            print(f"[KEYWORDS] YAKE failed: {e}, trying Gemini fallback", file=sys.stderr, flush=True)
    
    # Fallback/Alternative: Gemini extraction (slower, uses quota)
    if model:
        try:
            keyword_prompt = f"""
Extract the 3 most relevant keywords from this query for searching Islamic texts (Quran/Hadith).
Focus on core concepts, not common words.
Return ONLY the keywords separated by commas, nothing else.

Examples:
- Query: "How to deal with a difficult life partner" → marriage, patience, relationship
- Query: "Feeling anxious about the future" → anxiety, trust, future
- Query: "trouble setting boundaries with family and friends" → boundaries, family, relationships

Query: "{query}"
"""
            kw_response = model.generate_content(keyword_prompt)
            keywords_str = kw_response.text.strip()
            keyword_list = [k.strip() for k in keywords_str.split(',') if k.strip()][:3]
            
            # Cache successful extraction (1 hour TTL)
            await cache.set(cache_key, json.dumps(keyword_list), ttl=3600)
            print(f"[KEYWORDS] Extracted via Gemini: {keyword_list}", file=sys.stdout, flush=True)
            return keyword_list
            
        except Exception as e:
            print(f"[KEYWORDS] Gemini extraction failed: {e}", file=sys.stderr, flush=True)
    
    # Final fallback: Use custom extractor if we haven't already
    print(f"[KEYWORDS] Using final custom fallback", file=sys.stdout, flush=True)
    return extract_keywords_custom(query, max_keywords=3)


# Default model
DEFAULT_MODEL = 'gemini-2.0-flash-exp'

# Current selected model (can be changed via API)
_selected_model_id = DEFAULT_MODEL
_cached_model = None

def get_gemini_model(model_id: Optional[str] = None):
    """
    Get cached Gemini model instance with optional model selection.
    
    Args:
        model_id: Optional model ID to use. If None, uses currently selected model.
    
    Returns:
        Gemini model or None if unavailable
    """
    global _cached_model, _selected_model_id
    
    # If model_id is provided and different from current, clear cache
    if model_id and model_id != _selected_model_id:
        _selected_model_id = model_id
        _cached_model = None
        print(f"[GEMINI] Switching to model: {model_id}", file=sys.stdout, flush=True)
    
    # Return cached model if available
    if _cached_model is not None:
        return _cached_model
    
    if not API_KEY:
        print("[WARNING] GEMINI_API_KEY not found", file=sys.stderr, flush=True)
        return None
    
    try:
        genai.configure(api_key=API_KEY)
        _cached_model = genai.GenerativeModel(_selected_model_id)
        print(f"[SUCCESS] Gemini model '{_selected_model_id}' initialized and cached", file=sys.stdout, flush=True)
        return _cached_model
    except Exception as e:
        print(f"[ERROR] Error configuring Gemini model '{_selected_model_id}': {e}", file=sys.stderr, flush=True)
        return None

def get_current_model_id() -> str:
    """Get the currently selected model ID"""
    return _selected_model_id

def set_model(model_id: str) -> bool:
    """
    Set the current Gemini model.
    
    Args:
        model_id: Model ID to switch to
    
    Returns:
        True if successful, False otherwise
    """
    global _selected_model_id, _cached_model
    
    # Validate model ID
    valid_ids = [m['id'] for m in GEMINI_MODELS]
    if model_id not in valid_ids:
        print(f"[ERROR] Invalid model ID: {model_id}", file=sys.stderr, flush=True)
        return False
    
    # Clear cache and set new model
    _selected_model_id = model_id
    _cached_model = None
    
    print(f"[GEMINI] Model changed to: {model_id}", file=sys.stdout, flush=True)
    return True


# =============================================================================
# LIFECYCLE EVENTS
# =============================================================================

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Modern FastAPI lifecycle handler.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown")
    """
    # ========== STARTUP ==========
    print("[STARTUP] Connecting to cache service...", file=sys.stdout, flush=True)
    
    # Validate environment variables
    if not API_KEY:
        print("[WARNING] GEMINI_API_KEY not set - API will be unavailable", file=sys.stderr, flush=True)
    else:
        print("[SUCCESS] GEMINI_API_KEY found", file=sys.stdout, flush=True)
    
    # Connect to cache
    try:
        await cache.connect()
    except Exception as e:
        print(f"[WARNING] Cache connection failed: {e}", file=sys.stderr, flush=True)
    
    # Pre-initialize Gemini model
    get_gemini_model()
    
    # Pre-initialize keyword extractors
    if YAKE_AVAILABLE:
        get_yake_extractor()
        print("[STARTUP] YAKE extractor ready", file=sys.stdout, flush=True)
    else:
        print("[STARTUP] YAKE not available - using custom extractor", file=sys.stderr, flush=True)
    
    # Initialize custom extractor
    custom_ext = get_custom_extractor()
    if custom_ext:
        print("[STARTUP] Custom keyword extractor ready", file=sys.stdout, flush=True)
    else:
        print("[WARNING] Custom extractor unavailable - limited keyword extraction", file=sys.stderr, flush=True)
    
    print("[STARTUP] Application ready", file=sys.stdout, flush=True)
    
    # Automatic Startup Tests (Runs in background after server starts)
    async def run_startup_tests():
        """Runs endpoint tests after a short delay to allow server startup"""
        try:
            # Wait for server to be fully responsive
            await asyncio.sleep(5) 
            
            print("\n[STARTUP] Running automatic endpoint health checks...", file=sys.stdout, flush=True)
            
            # Determine Base URL
            port = int(os.getenv("PORT", 8000))
            if IS_SERVERLESS:
                base_url = "https://islamic-guidance-ai.vercel.app"
            else:
                base_url = f"http://localhost:{port}"
            
            # Import and run tests in a separate thread to not block event loop
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
                
            from tests.backend.test_endpoints import run_health_checks
            
            # Run synchronous tests in thread pool
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: run_health_checks(base_url))
            
        except Exception as e:
            print(f"[STARTUP] Error running automatic tests: {e}", file=sys.stderr, flush=True)

    # Schedule the test task
    asyncio.create_task(run_startup_tests())
    
    yield  # App runs here
    
    # ========== SHUTDOWN ==========
    print("[SHUTDOWN] Closing cache connection...", file=sys.stdout, flush=True)
    try:
        await cache.close()
    except Exception as e:
        print(f"[SHUTDOWN] Error closing cache: {e}", file=sys.stderr, flush=True)
    
    print("[SHUTDOWN] Cleanup complete", file=sys.stdout, flush=True)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def truncate_json_for_log(data, max_text_length=200):
    """
    Truncate long text fields in JSON while preserving structure.
    Used to make logs readable without massive text dumps.
    """
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > max_text_length:
                truncated = value[:max_text_length]
                result[key] = f"{truncated}... [TRUNCATED {len(value)-max_text_length} chars]"
            elif isinstance(value, (dict, list)):
                result[key] = truncate_json_for_log(value, max_text_length)
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        return [truncate_json_for_log(item, max_text_length) for item in data]
    return data

def validate_response_size(data: dict, max_size_bytes: int = 4_500_000) -> dict:
    """
    Validate and truncate response to stay within Vercel's 4.5MB limit.
    Issue #2 - P0
    
    Args:
        data: Response data dictionary
        max_size_bytes: Maximum allowed size in bytes
    
    Returns:
        Truncated data if necessary
    """
    json_str = json.dumps(data)
    size = len(json_str.encode('utf-8'))
    
    if size <= max_size_bytes:
        return data
    
    print(f"[WARNING] Response size {size} bytes exceeds limit, truncating", file=sys.stderr, flush=True)
    
    # Truncate citations first
    if 'citations' in data and len(data['citations']) > 5:
        data['citations'] = data['citations'][:5]
        print("[TRUNCATE] Reduced citations to 5", file=sys.stdout, flush=True)
    
    # If still too large, truncate answer
    json_str = json.dumps(data)
    size = len(json_str.encode('utf-8'))
    
    if size > max_size_bytes and 'answer' in data:
        max_answer_length = len(data['answer']) - (size - max_size_bytes) - 1000
        data['answer'] = data['answer'][:max_answer_length] + "... [Response truncated due to size limit]"
        print(f"[TRUNCATE] Reduced answer to {max_answer_length} chars", file=sys.stdout, flush=True)
    
    return data

# =============================================================================
# FASTAPI APPLICATION SETUP
# =============================================================================

app = FastAPI(
    title="Islamic Guidance AI",
    description="AI-powered Islamic guidance using Quran and Hadith",
    version="3.0.0",
    lifespan=lifespan
)

# Rate Limiting Setup (Using SlowAPI for standard endpoints, custom for /api/guidance)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initialize Vercel KV rate limiter for critical endpoints
vercel_rate_limiter = VercelKVRateLimiter(max_requests=100, window_seconds=3600)

# GZip Compression (Issue #14 - P2: Lowered threshold to 500 bytes)
app.add_middleware(GZipMiddleware, minimum_size=500)

# Get the port from the .env
port = os.getenv("PORT", 8000)

# CORS middleware configuration (Issue #17 - P3: Restricted origins)
allowed_origins = [
    "https://islamic-guidance-ai.vercel.app",
    "http://localhost:" + port,
    "http://127.0.0.1:" + port,
]

# Allow all origins in development
if not IS_SERVERLESS:
    allowed_origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Print startup configuration with diagnostics
print("="*80, file=sys.stdout, flush=True)
print("Loading IslamicGuideAI Backend Module (OPTIMIZED v2.1 with YAKE)...", file=sys.stdout, flush=True)
print(f"Environment: {'SERVERLESS (Vercel)' if IS_SERVERLESS else 'LOCAL DEVELOPMENT'}", file=sys.stdout, flush=True)
print(f"YAKE Available: {YAKE_AVAILABLE}", file=sys.stdout, flush=True)
print(f"Custom Extractor Available: {KeywordExtractorNoDeps is not None}", file=sys.stdout, flush=True)

# Print environment diagnostics
print("\n[ENVIRONMENT DIAGNOSTICS]", file=sys.stdout, flush=True)
print(f"  VERCEL: {os.getenv('VERCEL', 'Not set')}", file=sys.stdout, flush=True)
print(f"  VERCEL_ENV: {os.getenv('VERCEL_ENV', 'Not set')}", file=sys.stdout, flush=True)
print(f"  VERCEL_URL: {os.getenv('VERCEL_URL', 'Not set')}", file=sys.stdout, flush=True)
print(f"  AWS_LAMBDA_FUNCTION_NAME: {'Set' if os.getenv('AWS_LAMBDA_FUNCTION_NAME') else 'Not set'}", file=sys.stdout, flush=True)
print(f"  GEMINI_API_KEY: {'Set (length: ' + str(len(API_KEY)) + ')' if API_KEY else 'Not set'}", file=sys.stdout, flush=True)

print(f"\nCORS Origins: {allowed_origins}", file=sys.stdout, flush=True)
print("="*80, file=sys.stdout, flush=True)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class GuidanceRequest(BaseModel):
    """Request model for guidance endpoint"""
    query: str
    source: str = "both"  # Options: internal, external, both
    hadith_collection: Optional[List[str]] = None

class LogRequest(BaseModel):
    """Request model for frontend logging"""
    level: str
    message: str
    timestamp: str

class APIKeyRequest(BaseModel):
    """Request model for API key management"""
    apiKey: str

class SettingsRequest(BaseModel):
    """Request model for saving settings"""
    apiKey: Optional[str] = None
    theme: Optional[str] = None
    geminiModel: Optional[str] = None



# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Comprehensive health check with better error handling"""
    print("[HEALTH] Health check endpoint called", file=sys.stderr, flush=True)
    
    health_status = {
        "status": "healthy",
        "service": "IslamicGuideAI",
        "version": "3.0.0",
        "environment": "serverless" if IS_SERVERLESS else "development",
        "checks": {}
    }
    
    # Check extractors
    health_status["checks"]["yake_extractor"] = "Available" if YAKE_AVAILABLE else "Not installed"
    health_status["checks"]["custom_extractor"] = "Available" if KeywordExtractorNoDeps else "Unavailable"
    print(f"[HEALTH] YAKE: {health_status['checks']['yake_extractor']}, Custom: {health_status['checks']['custom_extractor']}", file=sys.stderr, flush=True)
    
    # Check Gemini
    try:
        model = get_gemini_model()
        gemini_status = "Available" if model else "Unavailable"
        health_status["checks"]["gemini_ai"] = gemini_status
        api_key_masked = f"...{API_KEY[-8:]}" if API_KEY and len(API_KEY) > 8 else "Not set"
        print(f"[HEALTH] Gemini AI: {gemini_status}, API Key: {api_key_masked}", file=sys.stderr, flush=True)
    except Exception as e:
        health_status["checks"]["gemini_ai"] = f"Error: {str(e)[:50]}"
        health_status["status"] = "degraded"
        print(f"[HEALTH] Gemini AI error: {str(e)[:100]}", file=sys.stderr, flush=True)
    
    # Check Cache (with ping() fix)
    try:
        ping_result = await cache.ping()
        cache_status = "Connected" if ping_result else "Not responding"
        health_status["checks"]["cache"] = cache_status
        print(f"[HEALTH] Cache: {cache_status}", file=sys.stderr, flush=True)
    except Exception as e:
        health_status["checks"]["cache"] = f"Error: {str(e)[:50]}"
        print(f"[HEALTH] Cache error: {str(e)[:100]}", file=sys.stderr, flush=True)
    
    # Check Quran API
    try:
        test_results = await search_quran_async("test", max_results=1)
        health_status["checks"]["quran_api"] = "Reachable"
        print(f"[HEALTH] Quran API: Reachable (test returned {len(test_results)} results)", file=sys.stderr, flush=True)
    except Exception as e:
        health_status["checks"]["quran_api"] = f"Error: {str(e)[:50]}"
        health_status["status"] = "degraded"
        print(f"[HEALTH] Quran API error: {str(e)[:100]}", file=sys.stderr, flush=True)

    # check for Hadith API
    try:
        test_results = await search_hadith_async(topic="test", collections=["eng-bukhari", "eng-muslim"], max_per_collection=1)
        health_status["checks"]["hadith_api"] = "Reachable"
        print(f"[HEALTH] Hadith API: Reachable (test returned {len(test_results)} results)", file=sys.stderr, flush=True)
    except Exception as e:
        health_status["checks"]["hadith_api"] = f"Error: {str(e)[:50]}"
        health_status["status"] = "degraded"
        print(f"[HEALTH] Hadith API error: {str(e)[:100]}", file=sys.stderr, flush=True)
    
    print(f"[HEALTH] Overall status: {health_status['status']}", file=sys.stderr, flush=True)
    return health_status

@app.get("/")
async def root():
    """
    Basic service info endpoint
    """
    return {
        "status": "ok",
        "service": "IslamicGuideAI",
        "version": "3.0.0",
        "environment": "serverless" if IS_SERVERLESS else "development",
        "ai_model": "gemini-2.0-flash-exp",
        "keyword_extractor": "YAKE" if YAKE_AVAILABLE else "Custom",
        "health_check": "/api/health"
    }

@app.post("/api/log")
async def log_frontend(request: LogRequest):
    """
    Endpoint to receive logs from frontend (Issue #8 - P1: Error isolation)
    Never crashes - always returns success to prevent cascade failures
    """
    try:
        # Map log levels to appropriate output streams
        log_output = sys.stderr if request.level.upper() in ['ERROR', 'WARNING'] else sys.stdout
        print(
            f"[FRONTEND {request.timestamp}] [{request.level.upper()}] {request.message}",
            file=log_output,
            flush=True
        )
        return {"status": "logged"}
    except Exception as e:
        # SILENT FAILURE - Never raise exceptions from this endpoint
        print(f"[LOG FAILURE] {e}", file=sys.stderr, flush=True)
        return {"status": "logged"}

@app.post("/api/guidance")
async def get_guidance(request: GuidanceRequest, req: Request):
    """
    Main endpoint for AI-powered Islamic guidance (FULLY OPTIMIZED with YAKE).
    
    All P0-P3 issues addressed + YAKE integration:
    - Issue #1: Search timeout reduced to 6s
    - Issue #2: Response size validation before return
    - Issue #3: Semaphore limiting concurrent hadith fetches to 5
    - Issue #4: YAKE keyword extraction (fast, no API quota usage)
    - Issue #5: Vercel KV-based rate limiting
    - Issue #10: Cache error handling with fallback
    - Issue #11: Retry logic and circuit breaker in services.py
    - Issue #13: Request deduplication via cache
    - Issue #22: Request ID tracking
    """
    # Generate unique request ID for tracking (Issue #22 - P3)
    request_id = str(uuid.uuid4())
    
    print("="*80, file=sys.stdout, flush=True)
    print(f"[REQUEST {request_id}] New guidance request", file=sys.stdout, flush=True)
    print(f"[GUIDANCE] Query: {request.query}", file=sys.stdout, flush=True)
    print(f"[GUIDANCE] Source: {request.source}, Collections: {request.hadith_collection or 'default'}", file=sys.stdout, flush=True)
    print("="*80, file=sys.stdout, flush=True)
    
    # Validation
    if not request.query or len(request.query) < 10:
        print(f"[REQUEST {request_id}] Query too short", file=sys.stderr, flush=True)
        raise HTTPException(
            status_code=400,
            detail="Query too short. Please provide at least 10 characters."
        )
    
    # Vercel KV-based rate limiting (Issue #5 - P0)
    client_ip = get_remote_address(req)
    if not await vercel_rate_limiter.check_rate_limit(client_ip):
        print(f"[REQUEST {request_id}] Rate limit exceeded for {client_ip}", file=sys.stderr, flush=True)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )
    
    # Lazy load model
    model = get_gemini_model()
    if not model:
        print(f"[REQUEST {request_id}] Gemini model not available", file=sys.stderr, flush=True)
        raise HTTPException(
            status_code=503,
            detail="AI model not available. Please check API key configuration."
        )
    
    # Request deduplication via cache (Issue #13 - P2)
    try:
        collections_key = ",".join(sorted(request.hadith_collection or []))
        cache_key = f"guidance_response:{request.query}:{request.source}:{collections_key}"
        
        cached_response = await cache.get(cache_key)
        if cached_response:
            print(f"[REQUEST {request_id}] Cache hit for query", file=sys.stdout, flush=True)
            return cached_response
    except Exception as e:
        # Cache error handling with fallback (Issue #10 - P1)
        print(f"[REQUEST {request_id}] Cache error (continuing without cache): {e}", file=sys.stderr, flush=True)
    
    try:
        context_text = ""
        citations = []
        quran_results = []
        unique_hadiths = []
        
        # =====================================================================
        # MODE 1: EXTERNAL SOURCES ONLY (No Gemini API)
        # =====================================================================
        if request.source == "external":
            print(f"[REQUEST {request_id}] EXTERNAL MODE: Using only Quran + Hadith APIs (NO Gemini)", file=sys.stdout, flush=True)
            
            # Extract keywords with YAKE (NO Gemini usage)
            keyword_list = await extract_keywords_with_cache(request.query, None, use_gemini=False)
            print(f"[REQUEST {request_id}] Using keywords: {keyword_list}", file=sys.stdout, flush=True)
            
            # Get selected Hadith collections
            selected_collections = request.hadith_collection or [
                "eng-bukhari",
                "eng-muslim",
                "eng-abudawud",
                "eng-tirmidhi",
                "eng-nasai",
                "eng-ibnmajah"
            ]
            
            # Create search tasks with concurrency limit
            semaphore = asyncio.Semaphore(5)
            
            async def search_with_semaphore(keyword):
                async with semaphore:
                    return await search_hadith_async(
                        keyword,
                        collections=selected_collections,
                        max_per_collection=1
                    )
            
            # Execute searches concurrently with timeout
            try:
                quran_task = search_quran_async(", ".join(keyword_list), max_results=3)
                hadith_tasks = [search_with_semaphore(kw) for kw in keyword_list]
                
                search_timeout = 6
                search_results = await asyncio.wait_for(
                    asyncio.gather(quran_task, *hadith_tasks, return_exceptions=True),
                    timeout=search_timeout
                )
                
                # Process Quran results
                if isinstance(search_results[0], Exception):
                    print(f"[REQUEST {request_id}] Quran search failed: {search_results[0]}", file=sys.stderr, flush=True)
                    quran_results = []
                else:
                    quran_results = search_results[0]
                    print(f"[REQUEST {request_id}] Found {len(quran_results)} Quran verses", file=sys.stdout, flush=True)
                
                # Process Hadith results
                all_hadith_results = []
                for idx, result in enumerate(search_results[1:], 1):
                    if isinstance(result, Exception):
                        print(f"[REQUEST {request_id}] Hadith search {idx} failed: {result}", file=sys.stderr, flush=True)
                    elif result:
                        all_hadith_results.extend(result)
                
                # Remove duplicate hadiths
                seen = set()
                unique_hadiths = []
                for hadith in all_hadith_results:
                    key = (hadith.get('book', ''), hadith.get('hadithnumber', ''))
                    if key not in seen:
                        seen.add(key)
                        unique_hadiths.append(hadith)
                
                print(f"[REQUEST {request_id}] Found {len(unique_hadiths)} unique hadiths", file=sys.stdout, flush=True)
                
            except asyncio.TimeoutError:
                print(f"[REQUEST {request_id}] Search timed out after {search_timeout}s", file=sys.stderr, flush=True)
                quran_results = []
                unique_hadiths = []
            
            # Build answer text from search results (NO Gemini processing)
            answer_text = ""
            
            if quran_results:
                answer_text += "**Quran Verses:**\n\n"
                for verse in quran_results:
                    verse_num = verse.get('number')
                    surah_num = verse.get('surahNumber')
                    verse_in_surah = verse.get('numberInSurah')
                    if isinstance(verse_num, int) and 1 <= verse_num <= 6236 and surah_num and verse_in_surah:
                        answer_text += f"- {verse['text']}\n  *(Surah {verse['surah']}, Verse {verse_in_surah})*\n\n"
                        citations.append({
                            "title": f"Quran {verse['surah']}:{verse_in_surah}",
                            "url": f"https://quran.com/{surah_num}:{verse_in_surah}"
                        })
            
            if unique_hadiths:
                answer_text += f"**Hadiths ({len(unique_hadiths)} found):**\n\n"
                for hadith in unique_hadiths:
                    answer_text += f"- {hadith['text']}\n  *({hadith['source']}, Hadith #{hadith['hadithnumber']})*\n\n"
                    citations.append({
                        "title": f"{hadith['source']} - Hadith {hadith['hadithnumber']}",
                        "url": hadith['citation_url']
                    })
            
            # If no results found, provide message
            if not answer_text:
                answer_text = "No text found from Quran or Hadith for your query. However, you can explore the citations below if available."
            
            # Return data WITHOUT using Gemini
            data = {
                "answer": answer_text,
                "citations": citations
            }
            
            print(f"[REQUEST {request_id}] EXTERNAL MODE: Returning {len(citations)} citations without Gemini processing", file=sys.stdout, flush=True)
            
            # Validate response size
            data = validate_response_size(data)
            
            # Cache successful response
            try:
                await cache.set(cache_key, data, ttl=1800)
            except Exception as e:
                print(f"[REQUEST {request_id}] Cache write error: {e}", file=sys.stderr, flush=True)
            
            print(f"[REQUEST {request_id}] Success - returning external sources only", file=sys.stdout, flush=True)
            print("="*80, file=sys.stdout, flush=True)
            
            return data
        
        # =====================================================================
        # MODE 2 & 3: INTERNAL (Gemini only) OR BOTH (Gemini + External)
        # =====================================================================
        
        # Perform Search if Source is Both
        if request.source == "both":
            print(f"[REQUEST {request_id}] BOTH MODE: Using Gemini + Quran + Hadith APIs", file=sys.stdout, flush=True)
            
            # Extract keywords with YAKE (Issue #4 - P0: Fast, no API usage)
            keyword_list = await extract_keywords_with_cache(request.query, model, use_gemini=False)
            print(f"[REQUEST {request_id}] Using keywords: {keyword_list}", file=sys.stdout, flush=True)
            
            # Get selected Hadith collections
            selected_collections = request.hadith_collection or [
                "eng-bukhari",
                "eng-muslim",
                "eng-abudawud",
                "eng-tirmidhi",
                "eng-nasai",
                "eng-ibnmajah"
            ]
            
            # Create search tasks with concurrency limit (Issue #3 - P0)
            semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent requests
            
            async def search_with_semaphore(keyword):
                async with semaphore:
                    return await search_hadith_async(
                        keyword,
                        collections=selected_collections,
                        max_per_collection=1
                    )
            
            # Execute searches concurrently with timeout (Issue #1 - P0: Reduced to 6s)
            try:
                quran_task = search_quran_async(", ".join(keyword_list), max_results=3)
                hadith_tasks = [search_with_semaphore(kw) for kw in keyword_list]
                
                search_timeout = 6  # seconds (Issue #1 - P0: Changed from 8 to 6)
                search_results = await asyncio.wait_for(
                    asyncio.gather(quran_task, *hadith_tasks, return_exceptions=True),
                    timeout=search_timeout
                )
                
                # Process Quran results
                if isinstance(search_results[0], Exception):
                    print(f"[REQUEST {request_id}] Quran search failed: {search_results[0]}", file=sys.stderr, flush=True)
                    quran_results = []
                else:
                    quran_results = search_results[0]
                    print(f"[REQUEST {request_id}] Found {len(quran_results)} Quran verses", file=sys.stdout, flush=True)
                
                # Process Hadith results
                all_hadith_results = []
                for idx, result in enumerate(search_results[1:], 1):
                    if isinstance(result, Exception):
                        print(f"[REQUEST {request_id}] Hadith search {idx} failed: {result}", file=sys.stderr, flush=True)
                    elif result:
                        all_hadith_results.extend(result)
                
                # Remove duplicate hadiths
                seen = set()
                unique_hadiths = []
                for hadith in all_hadith_results:
                    key = (hadith.get('book', ''), hadith.get('hadithnumber', ''))
                    if key not in seen:
                        seen.add(key)
                        unique_hadiths.append(hadith)
                
                print(f"[REQUEST {request_id}] Found {len(unique_hadiths)} unique hadiths", file=sys.stdout, flush=True)
                
            except asyncio.TimeoutError:
                print(f"[REQUEST {request_id}] Search timed out after {search_timeout}s", file=sys.stderr, flush=True)
                quran_results = []
                unique_hadiths = []
            
            # Build context from search results
            if quran_results:
                context_text += "\n Quran Verses:\n"
                for verse in quran_results:
                    # Validate verse number (Issue #18 - P3)
                    verse_num = verse.get('number')
                    surah_num = verse.get('surahNumber')
                    verse_in_surah = verse.get('numberInSurah')
                    if isinstance(verse_num, int) and 1 <= verse_num <= 6236 and surah_num and verse_in_surah:
                        context_text += f"- {verse['text']} (Surah {verse['surah']} {verse_in_surah})\n"
                        citations.append({
                            "title": f"Quran {verse['surah']}:{verse_in_surah}",
                            "url": f"https://quran.com/{surah_num}:{verse_in_surah}"
                        })
            
            if unique_hadiths:
                context_text += f"\n Hadiths (Found {len(unique_hadiths)}):\n"
                for hadith in unique_hadiths:
                    context_text += (
                        f"- {hadith['text']} "
                        f"({hadith['source']}, Hadith #{hadith['hadithnumber']})\n"
                    )
                    citations.append({
                        "title": f"{hadith['source']} - Hadith {hadith['hadithnumber']}",
                        "url": hadith['citation_url']
                    })
        elif request.source == "internal":
            print(f"[REQUEST {request_id}] INTERNAL MODE: Using only Gemini API (NO external sources)", file=sys.stdout, flush=True)
        
        # Construct Gemini prompt based on source selection
        base_instruction = """
You are an Islamic Guidance AI assistant. Provide helpful, empathetic Islamic perspective
to the user's question with wisdom from Islamic teachings.
"""
        
        if request.source == "internal":
            prompt = f"{base_instruction}\nUser Query: \"{request.query}\"\nUse your internal knowledge of Islamic teachings to provide guidance."
        else:  # both
            prompt = f"{base_instruction}\nUser Query: \"{request.query}\"\n\nCONTEXT:\n{context_text}\n\nCombine context with your knowledge."
        
        prompt += """

RESPONSE FORMAT:
If the query is NOT related to Islamic guidance, return:
{ "error": "This question is not related to Islamic guidance." }

Otherwise return JSON:
{
  "answer": "Your detailed, compassionate guidance here...",
  "citations": []
}
"""
        
        # Generate response with JSON format
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        response_text = response.text.strip()
        
        # Clean up JSON response
        if response_text.startswith("```"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        data = json.loads(response_text.strip())
        
        # Merge citations for "both" mode
        if "answer" in data and request.source == "both":
            existing_urls = {c.get("url") for c in data.get("citations", [])}
            for citation in citations:
                if citation["url"] not in existing_urls:
                    data.setdefault("citations", []).append(citation)
        
        # Validate response size before returning (Issue #2 - P0)
        data = validate_response_size(data)
        
        # Cache successful response (30 minutes)
        try:
            await cache.set(cache_key, data, ttl=1800)
        except Exception as e:
            print(f"[REQUEST {request_id}] Cache write error: {e}", file=sys.stderr, flush=True)
        
        print(f"[REQUEST {request_id}] Success - returning response", file=sys.stdout, flush=True)
        print("="*80, file=sys.stdout, flush=True)
        
        return data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[REQUEST {request_id}] Error: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        
        # Graceful degradation (Issue #19 - P3)
        # Try to return cached response for same query
        try:
            fallback_key = f"guidance_response:{request.query}:*"
            # In production, implement wildcard search or store last response
        except:
            pass
        
        error_msg = str(e).lower()
        if "quota" in error_msg or "429" in error_msg:
            raise HTTPException(status_code=429, detail="Rate limit exhausted")
        
        raise HTTPException(status_code=500, detail=f"Error: {str(e)[:100]}")

@app.get("/api/quran/search")
async def quran_search_endpoint(keyword: str):
    """Direct Quran search endpoint"""
    try:
        results = await search_quran_async(keyword, max_results=5)
        return {"results": results, "count": len(results)}
    except Exception as e:
        print(f"[QURAN ENDPOINT] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hadith/search")
async def hadith_search_endpoint(topic: str, collections: Optional[str] = None):
    """Direct Hadith search endpoint"""
    try:
        collection_list = None
        if collections:
            collection_list = [c.strip() for c in collections.split(',') if c.strip()]
        
        results = await search_hadith_async(topic, collections=collection_list, max_per_collection=3)
        return {"results": results, "count": len(results)}
    except Exception as e:
        print(f"[HADITH ENDPOINT] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test-keywords")
async def test_keywords_endpoint(text: str):
    """Test endpoint for keyword extraction"""
    try:
        if not text:
            raise HTTPException(status_code=400, detail="Text parameter required")
        
        # Test both extractors
        yake_keywords = extract_keywords_yake(text, max_keywords=5) if YAKE_AVAILABLE else []
        custom_keywords = extract_keywords_custom(text, max_keywords=5)
        
        return {
            "text": text,
            "yake_keywords": yake_keywords,
            "custom_keywords": custom_keywords,
            "yake_available": YAKE_AVAILABLE,
            "custom_available": KeywordExtractorNoDeps is not None
        }
    except Exception as e:
        print(f"[TEST KEYWORDS] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/save-settings")
async def save_settings(request: SettingsRequest):
    """
    Save all settings (API Key, Theme, Model) to .env file.
    """
    print("[SAVE-SETTINGS] Endpoint called", file=sys.stderr, flush=True)
    
    try:
        if IS_SERVERLESS:
            print("[SAVE-SETTINGS] Rejected - serverless environment", file=sys.stderr, flush=True)
            return {
                "success": False,
                "isProduction": True,
                "message": "Settings cannot be saved permanently in serverless environments.",
                "instructions": "Please set environment variables in your deployment platform.",
                "environment": os.getenv("VERCEL_ENV", "production")
            }
        
        # Mask API key for logging
        api_key_masked = f"...{request.apiKey[-8:]}" if request.apiKey and len(request.apiKey) > 8 else "None"
        print(f"[SAVE-SETTINGS] Saving - API Key: {api_key_masked}, Theme: {request.theme}, Model: {request.geminiModel}", file=sys.stderr, flush=True)
        
        # Find .env file path
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        print(f"[SAVE-SETTINGS] Env file path: {env_path}", file=sys.stderr, flush=True)
        
        # Read existing .env file
        env_lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()
            print(f"[SAVE-SETTINGS] Read {len(env_lines)} lines from existing .env", file=sys.stderr, flush=True)
        else:
            print(f"[SAVE-SETTINGS] .env file not found, creating new", file=sys.stderr, flush=True)
        
        # Helper to update or append key
        def update_env_var(lines, key, value):
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    found = True
                    break
            if not found:
                lines.append(f"{key}={value}\n")
            return lines

        # Update variables
        if request.apiKey:
            env_lines = update_env_var(env_lines, "GEMINI_API_KEY", request.apiKey.strip())
            os.environ["GEMINI_API_KEY"] = request.apiKey.strip()
            global API_KEY
            API_KEY = request.apiKey.strip()
            print(f"[SAVE-SETTINGS] Updated API Key: ...{API_KEY[-8:]}", file=sys.stderr, flush=True)
            
        if request.theme:
            env_lines = update_env_var(env_lines, "THEME", request.theme.strip())
            os.environ["THEME"] = request.theme.strip()
            print(f"[SAVE-SETTINGS] Updated Theme: {request.theme}", file=sys.stderr, flush=True)
            
        if request.geminiModel:
            env_lines = update_env_var(env_lines, "GEMINI_MODEL", request.geminiModel.strip())
            os.environ["GEMINI_MODEL"] = request.geminiModel.strip()
            set_model(request.geminiModel.strip())
            print(f"[SAVE-SETTINGS] Updated Gemini Model: {request.geminiModel}", file=sys.stderr, flush=True)

        # Write back to .env file
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(env_lines)
        print(f"[SAVE-SETTINGS] Successfully wrote {len(env_lines)} lines to .env", file=sys.stderr, flush=True)
        
        return {
            "success": True,
            "isProduction": False,
            "message": "Settings saved successfully.",
            "environment": "local"
        }
        
    except Exception as e:
        print(f"[SAVE-SETTINGS] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"Error saving settings: {str(e)[:100]}")

@app.get("/api/get-settings")
async def get_settings():
    """
    Get all settings from environment variables.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        # Mask key if in serverless/production
        if IS_SERVERLESS and api_key:
            api_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        
        print("Settings retrieved successfully.", file=sys.stderr, flush=True)
        print(f"Settings is apiKey {api_key[-8:]}...., theme {os.getenv('THEME', 'traditional')}, geminiModel {os.getenv('GEMINI_MODEL', DEFAULT_MODEL)}, isProduction {IS_SERVERLESS}", file=sys.stderr, flush=True)
            
        return {
        "apiKey": api_key,
            "theme": os.getenv("THEME", "traditional"),
            "geminiModel": os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
            "isProduction": IS_SERVERLESS
        }
    except Exception as e:
        print(f"[GET-SETTINGS] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving settings: {str(e)[:100]}")

@app.get("/api/example-prompt")
async def get_example_prompt():
    """
    Return a random example guidance prompt.
    """
    import random
    try:
        prompt = random.choice(EXAMPLE_PROMPTS)
        return {"prompt": prompt}
    except Exception as e:
        print(f"[EXAMPLE-PROMPT] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/clear-cache")
async def clear_cache_endpoint(pattern: Optional[str] = None):
    """
    Clear cache (admin endpoint for development/debugging)
    
    Args:
        pattern: Optional pattern to match (e.g., 'quran_search:*', 'guidance_response:*')
                 If not provided, clears common patterns
    """
    try:
        patterns_to_clear = []
        
        if pattern:
            patterns_to_clear = [pattern]
        else:
            # Clear common cache patterns
            patterns_to_clear = [
                "quran_search:*",
                "guidance_response:*",
                "keywords:*",
                "hadith_collection:*",
                "ratelimit:*"
            ]
        
        cleared_patterns = []
        for p in patterns_to_clear:
            await cache.clear_pattern(p)
            cleared_patterns.append(p)
        
        return {
            "success": True,
            "message": f"Cache cleared for {len(cleared_patterns)} patterns",
            "patterns": cleared_patterns
        }
        
    except Exception as e:
        print(f"[CLEAR-CACHE] Error: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error clearing cache: {str(e)[:100]}"
        )

@app.get("/api/admin/run-tests")
async def run_endpoint_tests():
    """
    Run endpoint health checks (admin endpoint)
    
    This endpoint triggers the test suite and returns results.
    Should be called AFTER the server is fully started.
    """
    try:
        # Import the test function
        try:
            from tests.backend.test_endpoints import run_health_checks
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Test module not found. Ensure tests/backend/test_endpoints.py exists."
            )
        
        # Determine base URL
        port = int(os.getenv("PORT", 8000))
        if IS_SERVERLESS:
            base_url = "https://islamic-guidance-ai.vercel.app"
        else:
            base_url = f"http://localhost:{port}"
        
        # Run tests (this will print to console)
        print(f"\n[ADMIN] Running endpoint tests against {base_url}...", file=sys.stdout, flush=True)
        
        # Note: run_health_checks prints to console and returns exit code
        # We can't easily capture the output, so we just trigger it
        exit_code = run_health_checks(base_url)
        
        return {
            "success": exit_code == 0,
            "message": "Tests completed. Check server logs for detailed results.",
            "base_url": base_url,
            "exit_code": exit_code
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[RUN-TESTS] Error: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error running tests: {str(e)[:100]}"
        )

# =============================================================================
# GEMINI MODEL MANAGEMENT ENDPOINTS
# =============================================================================

@app.get("/api/models")
async def get_models():
    """
    Get list of available Gemini models.
    
    Returns:
        List of models with their IDs, names, and token limits
    """
    try:
        return {
            "success": True,
            "models": GEMINI_MODELS,
            "current_model": get_current_model_id(),
            "default_model": DEFAULT_MODEL
        }
    except Exception as e:
        print(f"[MODELS] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"Error fetching models: {str(e)}")

@app.get("/api/models/current")
async def get_current_model():
    """
    Get the currently selected Gemini model.
    
    Returns:
        Current model information
    """
    try:
        current_id = get_current_model_id()
        current_model = next((m for m in GEMINI_MODELS if m['id'] == current_id), None)
        
        return {
            "success": True,
            "model": current_model,
            "model_id": current_id
        }
    except Exception as e:
        print(f"[MODELS] Error: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"Error getting current model: {str(e)}")

class ModelRequest(BaseModel):
    modelId: str

@app.post("/api/models/set")
async def set_current_model(request: ModelRequest):
    """
    Set the current Gemini model.
    
    Args:
        request: ModelRequest with modelId
    
    Returns:
        Success status and new model information
    """
    try:
        model_id = request.modelId.strip()
        
        if not model_id:
            raise HTTPException(status_code=400, detail="Model ID cannot be empty")
        
        # Set the model
        success = set_model(model_id)
        
        if not success:
            raise HTTPException(status_code=400, detail=f"Invalid model ID: {model_id}")
        
        # Get the new model info
        new_model = next((m for m in GEMINI_MODELS if m['id'] == model_id), None)
        
        return {
            "success": True,
            "message": f"Model changed to {new_model['name']}",
            "model": new_model,
            "note": "The new model will be used for all subsequent requests"
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SET-MODEL] Error: {e}", file=sys.stderr, flush=True)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error setting model: {str(e)[:100]}"
        )


# Mount static files for local development only
if not IS_SERVERLESS:
    try:
        frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
        if os.path.exists(frontend_path):
            app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
            print(f"[SUCCESS] Mounted static files from: {frontend_path}", file=sys.stdout, flush=True)
    except Exception as e:
        print(f"[ERROR] Error mounting static files: {e}", file=sys.stderr, flush=True)

# Main entry point for local development
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print("="*80, file=sys.stdout, flush=True)
    print(">>> Starting Islamic Guidance AI server...", file=sys.stdout, flush=True)
    print(f"[HOST] {host}", file=sys.stdout, flush=True)
    print(f"[PORT] {port}", file=sys.stdout, flush=True)
    print(f"[URL] http://localhost:{port}", file=sys.stdout, flush=True)
    print(f"[YAKE] {'Enabled' if YAKE_AVAILABLE else 'Not installed (pip install yake)'}", file=sys.stdout, flush=True)
    print(f"[CUSTOM EXTRACTOR] {'Available' if KeywordExtractorNoDeps else 'Unavailable'}", file=sys.stdout, flush=True)
    print("="*80, file=sys.stdout, flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")
