"""
Vercel Serverless Function Entry Point - Minimal Version for Debugging
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60, file=sys.stdout)
print("🚀 Python process starting...", file=sys.stdout)
print(f"Python version: {sys.version}", file=sys.stdout)
print(f"Working directory: {os.getcwd()}", file=sys.stdout)
print(f"Python path: {sys.path}", file=sys.stdout)
print("=" * 60, file=sys.stdout)

# Try importing FastAPI
try:
    print("Attempting to import FastAPI...", file=sys.stdout)
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    print("✅ FastAPI imported successfully", file=sys.stdout)
except ImportError as e:
    print(f"❌ FastAPI import failed: {e}", file=sys.stdout)
    # Create fallback handler
    def handler(request):
        return {
            'statusCode': 500,
            'body': f'FastAPI import failed: {str(e)}'
        }
    sys.exit(0)  # Don't crash, just exit gracefully

# Create minimal app
app = FastAPI(title="Islamic Guidance AI - Debug")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "status": "running",
        "message": "Minimal API is working!",
        "python_version": sys.version,
        "cwd": os.getcwd()
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/test")
async def test():
    return {
        "test": "success",
        "environment": dict(os.environ)
    }

# Export for Vercel
handler = app

print("✅ App initialized successfully", file=sys.stdout)
