import os
import json
import traceback
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai

# Import services
from backend.services import search_quran, search_hadith

# Load environment variables
load_dotenv()

# --- Logging Configuration ---
# Check if running in serverless environment (Vercel)
# Vercel sets 'VERCEL' env var to '1'
IS_SERVERLESS = os.getenv("VERCEL") == "1"

# Configure logging
try:
    handlers = [logging.StreamHandler()]
    
    # Only attempt file logging if NOT in serverless and we can write to disk
    if not IS_SERVERLESS:
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "backend")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "app.log")
            handlers.append(RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5))
        except Exception as e:
            # If file logging fails, fallback to console only and treat as serverless-like
            print(f"Warning: Failed to setup file logging: {e}")
            IS_SERVERLESS = True

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )
except Exception as e:
    # Fallback if basicConfig fails
    print(f"Critical Error setting up logging: {e}")
    # Ensure we have at least basic logging
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("IslamicGuideAI")
logger.info("Loading IslamicGuideAI Backend Module...")

# Helper function to truncate long JSON for logging
def truncate_json_for_log(data, max_text_length=200):
    """Truncate long text fields in JSON while preserving structure"""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > max_text_length:
                result[key] = value[:max_text_length] + f"... [TRUNCATED {len(value)-max_text_length} chars]"
            elif isinstance(value, (dict, list)):
                result[key] = truncate_json_for_log(value, max_text_length)
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        return [truncate_json_for_log(item, max_text_length) for item in data]
    return data

# Configure Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
model = None

try:
    if not API_KEY:
        logger.warning("GEMINI_API_KEY not found in .env")
    else:
        genai.configure(api_key=API_KEY)
        # Use gemini-2.0-flash as verified
        model = genai.GenerativeModel('gemini-2.0-flash')
        logger.info("Successfully configured Gemini 2.0 Flash model")
except Exception as e:
    logger.error(f"Error configuring model: {e}")
    # Don't crash, just leave model as None

app = FastAPI()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "service": "IslamicGuideAI", "version": "1.0.0"}

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GuidanceRequest(BaseModel):
    query: str
    source: str = "both" # internal, external, both
    hadith_collection: list = None  # Optional list of hadith book codes

class LogRequest(BaseModel):
    level: str
    message: str
    timestamp: str

@app.post("/api/log")
async def log_frontend(request: LogRequest):
    """
    Endpoint to receive logs from the frontend.
    """
    # In serverless environment, just log to console
    if IS_SERVERLESS:
        logger.log(
            getattr(logging, request.level.upper(), logging.INFO),
            f"[FRONTEND] {request.message}"
        )
        return {"status": "logged"}
    
    # In local environment, write to file
    try:
        if not IS_SERVERLESS:
            frontend_log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "frontend")
            os.makedirs(frontend_log_dir, exist_ok=True)
            frontend_log_file = os.path.join(frontend_log_dir, "frontend.log")
            
            log_entry = f"{request.timestamp} - FRONTEND - {request.level.upper()} - {request.message}\n"
            
            with open(frontend_log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        else:
            # Fallback to console in serverless
            logger.log(
                getattr(logging, request.level.upper(), logging.INFO),
                f"[FRONTEND] {request.message}"
            )
            
        return {"status": "logged"}
    except Exception as e:
        # Fallback to console if file write fails
        logger.error(f"Failed to write frontend log to file: {e}")
        logger.log(
            getattr(logging, request.level.upper(), logging.INFO),
            f"[FRONTEND] {request.message}"
        )
        return {"status": "logged_console_fallback"}

@app.post("/api/guidance")
async def get_guidance(request: GuidanceRequest):
    logger.info("="*80)
    logger.info(f"[USER REQUEST] Received guidance request")
    logger.info(f"Query: {request.query}")
    logger.info(f"Source: {request.source}")
    logger.info("="*80)
    
    if not request.query or len(request.query) < 10:
        logger.warning("Query validation failed: Query too short")
        raise HTTPException(status_code=400, detail="Query too short")
    
    if not model:
        logger.error("AI model not available")
        raise HTTPException(status_code=503, detail="AI model not available. Please check API key configuration.")

    try:
        # 1. Check relevance (skip if clearly irrelevant, but let's assume relevant for now to save a call or do it in one go)
        # We will do it in one go with the main prompt to be efficient.
        
        context_text = ""
        citations = []
        
        # 2. Perform Search if Source is External or Both
        if request.source in ["external", "both"]:
            logger.info("[KEYWORD EXTRACTION] Extracting keywords for search...")
            # Ask Gemini to extract keywords - improved to handle multi-word queries
            keyword_prompt = f"""
            Extract ALL relevant keywords from this query for searching Islamic texts (Quran/Hadith). 
            Include multi-word concepts as separate keywords.
            Return ONLY the keywords separated by commas.
            
            Examples:
            - Query: "good life partner" → life, partner, marriage, spouse
            - Query: "dealing with anxiety" → anxiety, worry, stress, peace
            
            Query: "{request.query}"
            """
            logger.info(f"[GEMINI REQUEST] Sending keyword extraction request")
            logger.info(f"[GEMINI REQUEST] Prompt: {keyword_prompt}")
            kw_response = model.generate_content(keyword_prompt)
            keywords = kw_response.text.strip()
            logger.info(f"[GEMINI RESPONSE] Extracted keywords: '{keywords}'")
            
            
            # Search Quran
            logger.info(f"[QURAN SEARCH] Searching Quran with keywords: '{keywords}'")
            quran_results = search_quran(keywords)
            logger.info(f"[QURAN SEARCH] Found {len(quran_results)} Quran verses")
            
            # Search Hadith - use all keywords for better search coverage
            # Convert comma-separated keywords to list and search for each
            keyword_list = [k.strip() for k in keywords.split(',') if k.strip()]
            all_hadith_results = []
            
            # Get selected hadith collections from request, default to Kutub al-Sittah
            selected_collections = request.hadith_collection or [
                "eng-bukhari", "eng-muslim", "eng-abudawud", 
                "eng-tirmidhi", "eng-nasai", "eng-ibnmajah"
            ]
            
            logger.info(f"[HADITH SEARCH] Using collections: {selected_collections}")
            logger.info(f"[HADITH SEARCH] Searching with {len(keyword_list)} keywords: {keyword_list}")
            for keyword in keyword_list:
                logger.info(f"[HADITH SEARCH] Searching Hadith with keyword: '{keyword}'")
                hadith_results = search_hadith(keyword, collections=selected_collections)
                if hadith_results:
                    all_hadith_results.extend(hadith_results)
                    logger.info(f"[HADITH SEARCH] Found {len(hadith_results)} Hadiths for keyword '{keyword}'")
            
            # Remove duplicates based on hadithnumber and book
            seen = set()
            unique_hadiths = []
            for h in all_hadith_results:
                key = (h.get('book', ''), h.get('hadithnumber', ''))
                if key not in seen:
                    seen.add(key)
                    unique_hadiths.append(h)
            
            logger.info(f"[HADITH SEARCH] Total unique Hadiths found: {len(unique_hadiths)}")
            
            # Build Context
            if quran_results:
                context_text += "\nQuran Verses:\n"
                for idx, q in enumerate(quran_results, 1):
                    context_text += f"- {q['text']} (Surah {q['surah']} {q['number']})\n"
                    citations.append({"title": f"Quran {q['surah']} {q['number']}", "url": f"https://quran.com/{q['number']}"})
                    # Log each verse details
                    logger.info(f"  [VERSE {idx}] Surah: {q['surah']}, Number: {q['number']}, Verse in Surah: {q['numberInSurah']}")
                    logger.info(f"  [VERSE {idx}] Text: {q['text'][:200]}{'...' if len(q['text']) > 200 else ''}")
            else:
                logger.info("[QURAN SEARCH] No Quran verses found")
            
            if unique_hadiths:
                context_text += f"\nHadiths (Found {len(unique_hadiths)}):\n"
                for idx, hadith in enumerate(unique_hadiths, 1):
                    context_text += f"- {hadith['text']} ({hadith['source']}, Hadith #{hadith['hadithnumber']})\n"
                    citations.append({
                        "title": f"{hadith['source']} - Hadith {hadith['hadithnumber']}", 
                        "url": hadith['citation_url']
                    })
                    # Log COMPLETE Hadith details being sent to Gemini (not truncated)
                    logger.info(f"  [HADITH {idx}] Collection: {hadith.get('book', 'Unknown')}")
                    logger.info(f"  [HADITH {idx}] Hadith Number: {hadith.get('hadithnumber', 'N/A')}")
                    logger.info(f"  [HADITH {idx}] Arabic Number: {hadith.get('arabicnumber', 'N/A')}")
                    logger.info(f"  [HADITH {idx}] Reference: {hadith.get('reference', {})}")
                    logger.info(f"  [HADITH {idx}] Citation URL: {hadith.get('citation_url', '')}")
                    logger.info(f"  [HADITH {idx}] FULL Text: {hadith.get('text', '')}")  # Full text, not truncated
            else:
                logger.info("[HADITH SEARCH] No Hadiths found")
                
            logger.info("="*80)
            logger.info(f"[SEARCH SUMMARY] Found {len(quran_results)} Quran verses and {len(unique_hadiths)} Hadiths")
            logger.info("="*80)

        # 3. Construct Main Prompt based on Source
        base_instruction = """
        You are an Islamic Guidance AI. Provide a helpful, empathetic Islamic perspective to the user's situation.
        """
        
        if request.source == "internal":
            prompt = f"""
            {base_instruction}
            User Query: "{request.query}"
            
            Use your internal knowledge to answer.
            """
        elif request.source == "external":
            # Check if we have any sources
            has_sources = bool(quran_results or unique_hadiths)
            
            if not has_sources:
                prompt = f"""
                {base_instruction}
                User Query: "{request.query}"
                
                CONTEXT FROM SOURCES:
                Quran: No sources found
                Hadith: No sources found
                
                INSTRUCTION: No specific Quran verses or Hadiths were found for this query in our search. 
                Politely inform the user that no specific sources were found, but offer general Islamic comfort and guidance.
                Suggest they can search directly on Quran.com and Sunnah.com for more specific references.
                """
            else:
                prompt = f"""
                {base_instruction}
                User Query: "{request.query}"
                
                CONTEXT FROM SOURCES:
                {context_text}
                
                INSTRUCTION: Use ONLY the provided context above to answer. Reference the specific sources provided.
                """
        else: # both
            prompt = f"""
            {base_instruction}
            User Query: "{request.query}"
            
            CONTEXT FROM SOURCES:
            {context_text}
            
            INSTRUCTION: Combine the provided context with your own knowledge to provide a comprehensive answer. Reference the sources if they are relevant.
            """

        # Add JSON formatting instruction
        prompt += """
        
        If the query is NOT related to life situations/Islam, return: { "error": "Irrelevant problem" }
        
        Otherwise return JSON:
        {
            "answer": "Your advice here...",
            "citations": [ ... ] 
        }
        """
        
        # Note: We append our manually found citations to the AI's response later, 
        # or we can ask AI to include them. Let's append them manually to ensure they are accurate to what we found.
        
        logger.info("[GEMINI REQUEST] Sending final guidance request to Gemini...")
        logger.info(f"[GEMINI REQUEST] Prompt: {prompt}")
        logger.info(f"[GEMINI REQUEST] Prompt length: {len(prompt)} characters")
        
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        logger.info("[GEMINI RESPONSE] Received response from Gemini")
        response_text = response.text
        logger.info(f"[GEMINI RESPONSE] Response length: {len(response_text)} characters")
        
        # Clean up
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        data = json.loads(response_text.strip())
        logger.info(f"[GEMINI RESPONSE] Parsed JSON successfully")
        
        # Log truncated response
        truncated_data = truncate_json_for_log(data, max_text_length=150)
        logger.info(f"[GEMINI RESPONSE] Response data: {json.dumps(truncated_data, indent=2)}")
        
        # Merge citations if valid answer
        if "answer" in data and request.source in ["external", "both"]:
            # We prioritize our found citations, but AI might have added some too (internal knowledge).
            # Let's just use ours for 'external' mode, and merge for 'both'.
            if request.source == "external":
                data["citations"] = citations
            else:
                # Merge avoiding duplicates (simple check)
                existing_urls = {c.get("url") for c in data.get("citations", [])}
                for c in citations:
                    if c["url"] not in existing_urls:
                        data.setdefault("citations", []).append(c)
        
        logger.info("[SUCCESS] Returning guidance response to user")
        logger.info("="*80)
        return data

    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)
        error_msg = str(e).lower()
        if "quota" in error_msg or "resource exhausted" in error_msg or "429" in error_msg:
            raise HTTPException(status_code=429, detail="API quota exceeded. Please try again later.")
        raise HTTPException(status_code=500, detail=f"Error generating guidance: {str(e)[:100]}")

# New API endpoints for Quran and Hadith search

@app.get("/api/quran/search")
async def quran_search_endpoint(keyword: str):
    """
    Search Quran verses using the external API via Python backend.
    """
    return search_quran(keyword)

@app.get("/api/hadith/search")
async def hadith_search_endpoint(topic: str, book: str = "bukhari"):
    """
    Search Hadiths for a topic within a given collection.
    """
    return search_hadith(topic, book)



@app.get("/api/get-api-key")
async def get_api_key():
    """
    Return the Gemini API key from environment for settings page.
    In serverless/production, this returns a masked version for security.
    """
    try:
        logger.info("[GET-API-KEY] Endpoint called")
        logger.info(f"[GET-API-KEY] IS_SERVERLESS: {IS_SERVERLESS}")
        logger.info(f"[GET-API-KEY] API_KEY exists: {bool(API_KEY)}")
        
        if IS_SERVERLESS:
            # In production, return masked key for security
            if API_KEY:
                masked_key = API_KEY[:8] + "..." + API_KEY[-4:] if len(API_KEY) > 12 else "***"
                logger.info(f"[GET-API-KEY] Returning masked key in serverless mode")
                return {"apiKey": masked_key, "isProduction": True}
            else:
                logger.warning("[GET-API-KEY] No API key found in serverless environment")
                return {"apiKey": "", "isProduction": True}
        else:
            # In development, return full key
            logger.info(f"[GET-API-KEY] Returning full key in development mode")
            return {"apiKey": API_KEY or "", "isProduction": False}
    except Exception as e:
        logger.error(f"[GET-API-KEY] Error: {str(e)}")
        logger.error(f"[GET-API-KEY] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving API key: {str(e)}"
        )

@app.post("/api/save-api-key")
async def save_api_key(request: Request):
    """
    Save API key to .env file (development only).
    Note: This endpoint is disabled in serverless/production environments.
    """
    try:
        logger.info("[SAVE-API-KEY] Endpoint called")
        logger.info(f"[SAVE-API-KEY] IS_SERVERLESS: {IS_SERVERLESS}")
        
        # Disable in serverless environment
        if IS_SERVERLESS:
            logger.warning("[SAVE-API-KEY] Attempted to save API key in serverless environment")
            raise HTTPException(
                status_code=403,
                detail="API key saving is disabled in production. Please set GEMINI_API_KEY environment variable in Vercel dashboard."
            )
        
        # Parse request body
        try:
            body = await request.json()
            logger.info(f"[SAVE-API-KEY] Request body parsed successfully")
        except Exception as e:
            logger.error(f"[SAVE-API-KEY] Failed to parse request body: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid JSON in request body")
        
        new_key = body.get("apiKey", "").strip()
        logger.info(f"[SAVE-API-KEY] API key length: {len(new_key) if new_key else 0}")
        
        if not new_key:
            logger.warning("[SAVE-API-KEY] Empty API key provided")
            raise HTTPException(status_code=400, detail="API key cannot be empty")
        
        # Path to .env in root directory (one level up from backend)
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        logger.info(f"[SAVE-API-KEY] .env path: {env_path}")
        
        # Read existing .env content
        env_lines = []
        key_found = False
        
        if os.path.exists(env_path):
            logger.info(f"[SAVE-API-KEY] .env file exists, reading...")
            with open(env_path, "r", encoding="utf-8") as f:
                env_lines = f.readlines()
            
            # Update existing key or mark for addition
            for i, line in enumerate(env_lines):
                if line.startswith("GEMINI_API_KEY="):
                    env_lines[i] = f"GEMINI_API_KEY={new_key}\n"
                    key_found = True
                    logger.info(f"[SAVE-API-KEY] Updated existing key at line {i}")
                    break
        else:
            logger.info(f"[SAVE-API-KEY] .env file doesn't exist, will create new")
        
        # Add new key if not found
        if not key_found:
            env_lines.append(f"GEMINI_API_KEY={new_key}\n")
            logger.info(f"[SAVE-API-KEY] Added new API key")
        
        # Write back to .env
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(env_lines)
        logger.info(f"[SAVE-API-KEY] Successfully wrote to .env file")
        
        # Reload environment (requires server restart for full effect)
        os.environ["GEMINI_API_KEY"] = new_key
        
        logger.info("[SAVE-API-KEY] API key updated successfully")
        return {"success": True, "message": "API key saved. Please restart the server for changes to take full effect."}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SAVE-API-KEY] Unexpected error: {str(e)}")
        logger.error(f"[SAVE-API-KEY] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error saving API key: {str(e)}")


# Mount static files (HTML, CSS, JS) - must be AFTER all API routes
# Note: In Vercel, static files are served directly by Vercel's CDN, not by the Python app
if not IS_SERVERLESS:
    # Only mount static files in local development
    frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")

if __name__ == "__main__":
    port = os.getenv("PORT", 8000)
    print("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=port)
    print("Server started on http://localhost:" + port)
