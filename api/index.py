"""
Vercel Serverless Function Entry Point
Handles all API requests for the Islamic Guidance AI application
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import backend modules
try:
    from backend.main import app as backend_app
except ImportError as e:
    print(f"[ERROR] Failed to import backend: {e}")
    # Create minimal app if import fails
    backend_app = FastAPI()
    
# Create main app instance
app = FastAPI(title="Islamic Guidance AI", version="1.0.0")

# Configure CORS for Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount backend routes
try:
    app.mount("/api", backend_app)
except Exception as e:
    print(f"[ERROR] Failed to mount backend: {e}")

# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {"status": "healthy", "message": "Islamic Guidance AI API"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "environment": os.getenv("VERCEL_ENV", "development"),
        "region": os.getenv("VERCEL_REGION", "unknown")
    }

# Error handler for all exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for better error logging"""
    print(f"[ERROR] Unhandled exception: {type(exc).__name__}: {str(exc)}")
    print(f"[ERROR] Request URL: {request.url}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )

# Export for Vercel
handler = app
