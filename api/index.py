"""
Vercel Serverless Function Entry Point for IslamicGuideAI Backend
This file adapts the FastAPI application to work with Vercel's serverless infrastructure.
"""

import sys
import os

# Add the parent directory to Python path so we can import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

try:
    print("Attempting to import backend.main...", flush=True)
    from backend.main import app
    print("Successfully imported backend.main", flush=True)
except Exception as e:
    import traceback
    print(f"Error importing backend.main: {e}", flush=True)
    traceback.print_exc()
    sys.stdout.flush()
    raise e

# Vercel expects a handler function or an ASGI app
# Since FastAPI is already an ASGI app, we can export it directly
# The handler will be automatically created by Vercel's Python runtime
handler = app
