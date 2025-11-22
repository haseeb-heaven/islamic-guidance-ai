"""
Main FastAPI Application
Core API endpoints for Islamic Guidance
"""

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
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
        try:
            app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
            logger.info(f"✅ Mounted static files from: {static_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not mount static files: {e}")

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
    data: Optional[Dict[str, Any]] = None

# ============================================================================
# SERVICE INITIALIZATION
# ============================================================================

def initialize_services():
    """Initialize all services with error handling"""
    services = {
        "gemini": None,
        "quran": None,
        "hadith": None
    }
    
    try:
        services["gemini"] = GeminiService()
        logger.info("✅ Gemini service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Gemini service initialization failed: {e}")
    
    try:
        services["quran"] = QuranService()
        logger.info("✅ Quran service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Quran service initialization failed: {e}")
    
    try:
        services["hadith"] = HadithService()
        logger.info("✅ Hadith service initialized")
    except Exception as e:
        logger.warning(f"⚠️ Hadith service initialization failed: {e}")
    
    return services

# Initialize services
services = initialize_services()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    if not IS_VERCEL:
        index_file = BASE_DIR / "frontend" / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    
    return {
        "message": "Islamic Guidance AI API",
        "status": "running",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    api_key_present = bool(os.getenv("GEMINI_API_KEY"))
    
    return {
        "status": "healthy",
        "services": {
            "gemini": services["gemini"] is not None,
            "quran": services["quran"] is not None,
            "hadith": services["hadith"] is not None
        },
        "environment": "vercel" if IS_VERCEL else "local",
        "api_key_configured": api_key_present
    }

@app.post("/api/guidance")
async def get_guidance(request: GuidanceRequest):
    """
    Main guidance endpoint
    Returns Islamic guidance based on Quran, Hadith, and AI
    """
    try:
        logger.info(f"📥 Guidance request: {request.query[:50]}...")
        
        # Check if Gemini service is available for AI requests
        if request.source in ["ai", "both"] and not services["gemini"]:
            logger.warning("⚠️ AI guidance requested but Gemini service unavailable")
            if request.source == "ai":
                raise HTTPException(
                    status_code=503,
                    detail="AI service not available. Please configure GEMINI_API_KEY or use 'external' source."
                )
        
        results = {
            "query": request.query,
            "guidance": "",
            "quran_verses": [],
            "hadith_references": [],
            "source": request.source
        }
        
        # Get AI guidance if requested
        if request.source in ["ai", "both"] and services["gemini"]:
            try:
                logger.info("🤖 Requesting AI guidance...")
                ai_guidance = await services["gemini"].get_guidance(
                    request.query,
                    include_sources=(request.source == "both")
                )
                results["guidance"] = ai_guidance
                logger.info("✅ AI guidance generated")
            except Exception as e:
                logger.error(f"❌ AI guidance failed: {e}")
                results["guidance"] = f"AI service temporarily unavailable: {str(e)}"
        
        # Get external sources if requested
        if request.source in ["external", "both"]:
            # Search Quran
            if services["quran"]:
                try:
                    logger.info("📖 Searching Quran...")
                    quran_results = await services["quran"].search(request.query)
                    results["quran_verses"] = parse_quran_response(quran_results)
                    logger.info(f"✅ Found {len(results['quran_verses'])} Quran verses")
                except Exception as e:
                    logger.error(f"❌ Quran search failed: {e}")
            
            # Search Hadith
            if services["hadith"]:
                try:
                    logger.info("📚 Searching Hadith...")
                    hadith_results = await services["hadith"].search(
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
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

@app.get("/api/quran/search")
async def search_quran(keyword: str, limit: int = 10):
    """Search Quran verses by keyword"""
    try:
        if not services["quran"]:
            raise HTTPException(
                status_code=503,
                detail="Quran service not available"
            )
        
        results = await services["quran"].search(keyword, limit=limit)
        return parse_quran_response(results)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Quran search error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Quran search failed: {str(e)}"
        )

@app.get("/api/hadith/search")
async def search_hadith(
    topic: str,
    collections: Optional[List[str]] = None,
    limit: int = 10
):
    """Search Hadith by topic"""
    try:
        if not services["hadith"]:
            raise HTTPException(
                status_code=503,
                detail="Hadith service not available"
            )
        
        if collections is None:
            collections = ["eng-bukhari", "eng-muslim"]
        
        results = await services["hadith"].search(
            topic,
            collections=collections,
            limit=limit
        )
        return parse_hadith_response(results)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Hadith search error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Hadith search failed: {str(e)}"
        )

@app.post("/api/save-api-key")
async def save_api_key(request: APIKeyRequest):
    """
    Save API key (DISABLED on Vercel for security)
    Use Vercel environment variables instead
    """
    try:
        if IS_VERCEL:
            logger.info("⚠️ API key save attempted on Vercel (disabled)")
            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "message": "API key saving is disabled on Vercel for security reasons.",
                    "instructions": "Please set GEMINI_API_KEY in Vercel Dashboard:\n1. Go to your project settings\n2. Navigate to Environment Variables\n3. Add GEMINI_API_KEY with your key\n4. Redeploy your application",
                    "dashboard_url": "https://vercel.com/dashboard"
                }
            )
        
        # Local development only
        logger.info("💾 Saving API key locally...")
        env_path = BASE_DIR / ".env"
        
        # Read existing content
        env_content = {}
        if env_path.exists():
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_content[key.strip()] = value.strip()
        
        # Update API key
        env_content['GEMINI_API_KEY'] = request.api_key
        
        # Write back
        with open(env_path, 'w', encoding='utf-8') as f:
            f.write("# Environment Variables\n")
            f.write("# Generated by Islamic Guidance AI\n\n")
            for key, value in env_content.items():
                f.write(f"{key}={value}\n")
        
        # Update current environment
        os.environ['GEMINI_API_KEY'] = request.api_key
        
        # Reinitialize Gemini service
        try:
            services["gemini"] = GeminiService()
            logger.info("✅ Gemini service reinitialized with new API key")
        except Exception as e:
            logger.error(f"❌ Failed to reinitialize Gemini service: {e}")
        
        logger.info("✅ API key saved successfully")
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "API key saved successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to save API key: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save API key: {str(e)}"
        )

@app.get("/api/get-api-key")
async def get_api_key():
    """Get API key status (returns masked key)"""
    try:
        api_key = os.getenv("GEMINI_API_KEY", "")
        
        if not api_key:
            logger.info("ℹ️ No API key configured")
            return JSONResponse(
                status_code=200,
                content={
                    "has_key": False,
                    "api_key": "",
                    "message": "No API key configured",
                    "instructions": "Please configure GEMINI_API_KEY" + (
                        " in Vercel Dashboard" if IS_VERCEL else " in settings"
                    )
                }
            )
        
        # Return masked key for security
        if len(api_key) > 12:
            masked_key = api_key[:8] + "..." + api_key[-4:]
        else:
            masked_key = "***"
        
        logger.info("✅ API key status retrieved")
        return JSONResponse(
            status_code=200,
            content={
                "has_key": True,
                "api_key": masked_key,
                "message": "API key is configured",
                "environment": "vercel" if IS_VERCEL else "local"
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get API key status: {e}")
        # Don't fail completely - return safe response
        return JSONResponse(
            status_code=200,
            content={
                "has_key": False,
                "api_key": "",
                "message": f"Error checking API key: {str(e)}"
            }
        )

@app.post("/api/log")
async def log_message(request: LogRequest):
    """
    Client-side logging endpoint
    Logs are sent to stdout (Vercel logs)
    """
    try:
        log_level = getattr(logging, request.level.upper(), logging.INFO)
        
        # Format log message
        message = f"[CLIENT] {request.message}"
        if request.data:
            message += f" | Data: {json.dumps(request.data, default=str)}"
        
        logger.log(log_level, message)
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "logged": True}
        )
        
    except Exception as e:
        # Don't fail the client request if logging fails
        logger.error(f"❌ Logging error: {e}")
        return JSONResponse(
            status_code=200,
            content={"success": False, "error": str(e), "logged": False}
        )

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning(f"⚠️ HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": str(request.url.path)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"❌ Unhandled error: {type(exc).__name__}: {str(exc)}")
    logger.error(f"📍 Request: {request.method} {request.url.path}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url.path)
        }
    )

# ============================================================================
# STARTUP/SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("=" * 60)
    logger.info("🚀 Islamic Guidance AI starting...")
    logger.info(f"📍 Environment: {'Vercel' if IS_VERCEL else 'Local'}")
    logger.info(f"📍 Base directory: {BASE_DIR}")
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        logger.info("✅ GEMINI_API_KEY configured")
    else:
        logger.warning("⚠️ GEMINI_API_KEY not configured - AI features will be limited")
    
    # Log service status
    logger.info(f"📊 Service Status:")
    logger.info(f"   - Gemini AI: {'✅ Ready' if services['gemini'] else '❌ Not Available'}")
    logger.info(f"   - Quran Search: {'✅ Ready' if services['quran'] else '❌ Not Available'}")
    logger.info(f"   - Hadith Search: {'✅ Ready' if services['hadith'] else '❌ Not Available'}")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("👋 Islamic Guidance AI shutting down...")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"🌐 Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
