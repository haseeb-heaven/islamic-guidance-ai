"""
Main FastAPI Application
Core API endpoints for Islamic Guidance
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from typing import List, Optional
import os
import json
import logging
from pathlib import Path
import sys

# Import services
try:
    from .services import QuranService, HadithService, GeminiService
    from .api_parsers import parse_quran_response, parse_hadith_response
except ImportError:
    from services import QuranService, HadithService, GeminiService
    from api_parsers import parse_quran_response, parse_hadith_response

# ============================================================================
# CONFIGURATION
# ============================================================================

# Detect environment
IS_VERCEL = os.getenv("VERCEL_ENV") is not None
BASE_DIR = Path(__file__).parent.parent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============================================================================
# APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="Islamic Guidance AI API",
    description="AI-powered Islamic guidance based on Quran and Hadith",
    version="1.0.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files only in local development
if not IS_VERCEL:
    static_path = BASE_DIR / "frontend"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
        logger.info(f"✅ Mounted static files from: {static_path}")

# ============================================================================
# DATA MODELS
# ============================================================================

class GuidanceRequest(BaseModel):
    """Request model for guidance endpoint"""
    query: str = Field(..., min_length=1, max_length=1000)
    source: str = Field(default="both", pattern="^(ai|external|both)$")
    hadith_collection: List[str] = Field(default=["eng-bukhari", "eng-muslim"])
    
    @validator('query')
    def query_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()

class APIKeyRequest(BaseModel):
    """Request model for API key"""
    api_key: str = Field(..., min_length=10)

class LogRequest(BaseModel):
    """Request model for logging"""
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    message: str = Field(..., min_length=1, max_length=5000)
    data: Optional[dict] = None

# ============================================================================
# SERVICE INITIALIZATION
# ============================================================================

try:
    gemini_service = GeminiService()
    quran_service = QuranService()
    hadith_service = HadithService()
    logger.info("✅ All services initialized successfully")
except Exception as e:
    logger.error(f"❌ Service initialization failed: {e}")
    gemini_service = None
    quran_service = None
    hadith_service = None

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    if not IS_VERCEL:
        return FileResponse(BASE_DIR / "frontend" / "index.html")
    return {
        "message": "Islamic Guidance AI API",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "gemini": gemini_service is not None,
            "quran": quran_service is not None,
            "hadith": hadith_service is not None
        },
        "environment": "vercel" if IS_VERCEL else "local"
    }

@app.post("/api/guidance")
async def get_guidance(request: GuidanceRequest):
    """
    Main guidance endpoint
    Returns Islamic guidance based on Quran, Hadith, and AI
    """
    try:
        logger.info(f"📥 Guidance request: {request.query[:50]}...")
        
        # Validate services
        if not gemini_service:
            raise HTTPException(
                status_code=503,
                detail="AI service not available. Please check GEMINI_API_KEY."
            )
        
        results = {
            "query": request.query,
            "guidance": "",
            "quran_verses": [],
            "hadith_references": [],
            "source": request.source
        }
        
        # Get AI guidance if requested
        if request.source in ["ai", "both"]:
            try:
                ai_guidance = await gemini_service.get_guidance(
                    request.query,
                    include_sources=(request.source == "both")
                )
                results["guidance"] = ai_guidance
                logger.info("✅ AI guidance generated")
            except Exception as e:
                logger.error(f"❌ AI guidance failed: {e}")
                results["guidance"] = f"AI service error: {str(e)}"
        
        # Get external sources if requested
        if request.source in ["external", "both"]:
            # Search Quran
            if quran_service:
                try:
                    quran_results = await quran_service.search(request.query)
                    results["quran_verses"] = parse_quran_response(quran_results)
                    logger.info(f"✅ Found {len(results['quran_verses'])} Quran verses")
                except Exception as e:
                    logger.error(f"❌ Quran search failed: {e}")
            
            # Search Hadith
            if hadith_service:
                try:
                    hadith_results = await hadith_service.search(
                        request.query,
                        collections=request.hadith_collection
                    )
                    results["hadith_references"] = parse_hadith_response(hadith_results)
                    logger.info(f"✅ Found {len(results['hadith_references'])} Hadith references")
                except Exception as e:
                    logger.error(f"❌ Hadith search failed: {e}")
        
        return JSONResponse(content=results)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Guidance endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/quran/search")
async def search_quran(keyword: str, limit: int = 10):
    """Search Quran verses by keyword"""
    try:
        if not quran_service:
            raise HTTPException(status_code=503, detail="Quran service not available")
        
        results = await quran_service.search(keyword, limit=limit)
        return parse_quran_response(results)
    except Exception as e:
        logger.error(f"❌ Quran search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hadith/search")
async def search_hadith(
    topic: str,
    collections: Optional[List[str]] = None,
    limit: int = 10
):
    """Search Hadith by topic"""
    try:
        if not hadith_service:
            raise HTTPException(status_code=503, detail="Hadith service not available")
        
        if collections is None:
            collections = ["eng-bukhari", "eng-muslim"]
        
        results = await hadith_service.search(topic, collections=collections, limit=limit)
        return parse_hadith_response(results)
    except Exception as e:
        logger.error(f"❌ Hadith search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/save-api-key")
async def save_api_key(request: APIKeyRequest):
    """
    Save API key (DISABLED on Vercel for security)
    Use Vercel environment variables instead
    """
    if IS_VERCEL:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "message": "API key saving disabled on Vercel. Use environment variables instead.",
                "instructions": "Set GEMINI_API_KEY in Vercel Dashboard > Settings > Environment Variables"
            }
        )
    
    try:
        # Save to .env file in local development
        env_path = BASE_DIR / ".env"
        
        # Read existing content
        env_content = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_content[key.strip()] = value.strip()
        
        # Update API key
        env_content['GEMINI_API_KEY'] = request.api_key
        
        # Write back
        with open(env_path, 'w') as f:
            f.write("# Environment Variables\n")
            for key, value in env_content.items():
                f.write(f"{key}={value}\n")
        
        # Update environment
        os.environ['GEMINI_API_KEY'] = request.api_key
        
        # Reinitialize Gemini service
        global gemini_service
        gemini_service = GeminiService()
        
        logger.info("✅ API key saved successfully")
        return {"success": True, "message": "API key saved successfully"}
        
    except Exception as e:
        logger.error(f"❌ Failed to save API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-api-key")
async def get_api_key():
    """Get API key status (returns masked key)"""
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        
        if not api_key:
            return {
                "has_key": False,
                "message": "No API key configured"
            }
        
        # Return masked key
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        
        return {
            "has_key": True,
            "api_key": masked_key,
            "message": "API key is configured"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get API key: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/log")
async def log_message(request: LogRequest):
    """
    Client-side logging endpoint
    """
    try:
        log_level = getattr(logging, request.level.upper(), logging.INFO)
        
        # Format log message
        message = f"[CLIENT] {request.message}"
        if request.data:
            message += f" | Data: {json.dumps(request.data)}"
        
        logger.log(log_level, message)
        
        return {"success": True, "logged": True}
        
    except Exception as e:
        # Don't fail the client request if logging fails
        logger.error(f"❌ Logging error: {e}")
        return {"success": False, "error": str(e)}

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"⚠️ HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"❌ Unhandled error: {type(exc).__name__}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )

# ============================================================================
# STARTUP EVENT
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("🚀 Islamic Guidance AI starting...")
    logger.info(f"📍 Environment: {'Vercel' if IS_VERCEL else 'Local'}")
    logger.info(f"📍 Base directory: {BASE_DIR}")
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        logger.info("✅ GEMINI_API_KEY found")
    else:
        logger.warning("⚠️ GEMINI_API_KEY not found")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
