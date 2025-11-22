"""
Vercel Serverless Function Entry Point
Handles all API requests for the Islamic Guidance AI application
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sys
import os
from pathlib import Path
import logging

# Configure logging for Vercel
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import backend app
try:
    from backend.main import app as backend_app
    logger.info("✅ Backend app imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import backend: {e}")
    # Create minimal fallback app
    backend_app = FastAPI()
    
    @backend_app.get("/")
    async def fallback_root():
        return {"error": "Backend failed to initialize", "details": str(e)}

# Detect environment
IS_VERCEL = os.getenv("VERCEL_ENV") is not None
logger.info(f"📍 Environment: {'Vercel' if IS_VERCEL else 'Local'}")

# Create main app instance
app = FastAPI(
    title="Islamic Guidance AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Islamic Guidance AI API",
        "status": "running",
        "version": "1.0.0",
        "environment": "vercel" if IS_VERCEL else "local",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "guidance": "/api/guidance",
            "quran_search": "/api/quran/search",
            "hadith_search": "/api/hadith/search"
        }
    }

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    api_key_status = "configured" if os.getenv("GEMINI_API_KEY") else "missing"
    
    return {
        "status": "healthy",
        "environment": "vercel" if IS_VERCEL else "local",
        "api_key": api_key_status,
        "timestamp": __import__("datetime").datetime.now().isoformat()
    }

# Mount backend routes
try:
    app.mount("/api", backend_app)
    logger.info("✅ Backend routes mounted successfully")
except Exception as e:
    logger.error(f"❌ Failed to mount backend: {e}")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions"""
    logger.error(f"❌ Unhandled exception: {type(exc).__name__}: {str(exc)}")
    logger.error(f"📍 Request URL: {request.url}")
    logger.error(f"📍 Request method: {request.method}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url.path)
        }
    )

# Export for Vercel
handler = app
