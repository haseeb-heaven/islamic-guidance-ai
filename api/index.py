"""
Vercel Serverless Function Entry Point
Handles all API requests for the Islamic Guidance AI application
"""

import sys
import os
from pathlib import Path

# CRITICAL: Add parent directory BEFORE any imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure basic logging FIRST
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)
logger = logging.getLogger(__name__)

# Log startup
logger.info("=" * 60)
logger.info("🚀 Vercel Function Starting...")
logger.info(f"📍 Python Path: {sys.path}")
logger.info(f"📍 Working Dir: {os.getcwd()}")
logger.info("=" * 60)

# Try to import FastAPI
try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    logger.info("✅ FastAPI imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import FastAPI: {e}")
    raise

# Try to import backend with detailed error tracking
import_errors = []
try:
    from backend.main import app as backend_app
    logger.info("✅ Backend app imported successfully")
    HAS_BACKEND = True
except Exception as e:
    import_error = {
        "error": str(e),
        "type": type(e).__name__,
        "path": sys.path,
        "cwd": os.getcwd()
    }
    import_errors.append(import_error)
    logger.error(f"❌ Failed to import backend: {e}")
    logger.error(f"❌ Error type: {type(e).__name__}")
    logger.error(f"❌ Current path: {sys.path}")
    logger.error(f"❌ CWD: {os.getcwd()}")
    HAS_BACKEND = False
    backend_app = None

# Create main app
app = FastAPI(
    title="Islamic Guidance AI",
    version="1.0.0"
)

# CORS
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
    response = {
        "name": "Islamic Guidance AI",
        "status": "running",
        "backend_loaded": HAS_BACKEND,
        "version": "1.0.0"
    }
    
    # Add diagnostics if backend failed to load
    if not HAS_BACKEND and import_errors:
        response["import_errors"] = import_errors
    
    return response

# Health check
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "backend": "loaded" if HAS_BACKEND else "failed",
        "api_key": "configured" if os.getenv("GEMINI_API_KEY") else "missing"
    }

# Mount backend if available
if HAS_BACKEND and backend_app:
    try:
        app.mount("/api", backend_app)
        logger.info("✅ Backend mounted at /api")
    except Exception as e:
        logger.error(f"❌ Failed to mount backend: {e}")

# Error handler
@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    logger.error(f"❌ Error: {type(exc).__name__}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": type(exc).__name__
        }
    )

# Export for Vercel
handler = app

logger.info("✅ Vercel function initialized")
