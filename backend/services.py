"""
Service Layer for External APIs
Handles Quran, Hadith, and Gemini AI interactions
"""

import httpx
import os
import logging
from typing import List, Dict, Optional
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)

# ============================================================================
# GEMINI AI SERVICE
# ============================================================================

class GeminiService:
    """Service for interacting with Google Gemini AI"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            logger.error("❌ GEMINI_API_KEY not found in environment")
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        logger.info("✅ GeminiService initialized")
    
    async def get_guidance(self, query: str, include_sources: bool = True) -> str:
        """
        Get Islamic guidance from Gemini AI
        
        Args:
            query: User's question
            include_sources: Whether to request citations
        
        Returns:
            AI-generated guidance text
        """
        try:
            prompt = self._build_prompt(query, include_sources)
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}?key={self.api_key}",
                    json={
                        "contents": [{
                            "parts": [{"text": prompt}]
                        }],
                        "generationConfig": {
                            "temperature": 0.7,
                            "topK": 40,
                            "topP": 0.95,
                            "maxOutputTokens": 2048,
                        }
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract text from response
                if "candidates" in data and len(data["candidates"]) > 0:
                    candidate = data["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        text = candidate["content"]["parts"][0].get("text", "")
                        return text.strip()
                
                logger.warning("⚠️ Unexpected Gemini response format")
                return "Unable to generate guidance at this time."
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Gemini API HTTP error: {e.response.status_code}")
            raise Exception(f"Gemini API error: {e.response.status_code}")
        except httpx.TimeoutException:
            logger.error("❌ Gemini API timeout")
            raise Exception("Request timed out. Please try again.")
        except Exception as e:
            logger.error(f"❌ Gemini service error: {e}")
            raise Exception(f"AI service error: {str(e)}")
    
    def _build_prompt(self, query: str, include_sources: bool) -> str:
        """Build the prompt for Gemini AI"""
        base_prompt = f"""You are an Islamic guidance assistant. Provide compassionate, accurate advice based on Quran and authentic Hadith.

User Question: {query}

Please provide:
1. Direct, empathetic answer to the question
2. Islamic perspective and guidance
3. Practical advice where applicable"""

        if include_sources:
            base_prompt += """
4. Relevant Quran verses (with Surah and Ayah numbers)
5. Relevant Hadith references (with collection and book)

Format citations as: [Surah Name Chapter:Verse] or [Collection - Book Number:Hadith Number]"""

        return base_prompt

# ============================================================================
# QURAN API SERVICE
# ============================================================================

class QuranService:
    """Service for searching and retrieving Quran verses"""
    
    def __init__(self):
        self.base_url = "https://api.quran.com/api/v4"
        self.timeout = httpx.Timeout(15.0, connect=5.0)
        logger.info("✅ QuranService initialized")
    
    async def search(self, keyword: str, limit: int = 10) -> Dict:
        """
        Search Quran verses by keyword
        
        Args:
            keyword: Search term
            limit: Maximum results to return
        
        Returns:
            Search results from Quran API
        """
        try:
            params = {
                "q": keyword,
                "size": min(limit, 20),
                "page": 1
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/search",
                    params=params
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Quran API HTTP error: {e.response.status_code}")
            return {"search": {"results": []}}
        except Exception as e:
            logger.error(f"❌ Quran service error: {e}")
            return {"search": {"results": []}}
    
    async def get_verse(self, chapter: int, verse: int) -> Optional[Dict]:
        """Get a specific verse"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/verses/by_key/{chapter}:{verse}"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"❌ Error getting verse {chapter}:{verse}: {e}")
            return None

# ============================================================================
# HADITH API SERVICE
# ============================================================================

class HadithService:
    """Service for searching and retrieving Hadith"""
    
    def __init__(self):
        self.base_url = "https://api.sunnah.com/v1"
        self.timeout = httpx.Timeout(15.0, connect=5.0)
        self.collections = {
            "eng-bukhari": "Sahih Bukhari",
            "eng-muslim": "Sahih Muslim",
            "eng-abudawud": "Abu Dawud",
            "eng-tirmidhi": "Tirmidhi",
            "eng-nasai": "Nasa'i",
            "eng-ibnmajah": "Ibn Majah"
        }
        logger.info("✅ HadithService initialized")
    
    async def search(
        self,
        query: str,
        collections: List[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search Hadith across collections
        
        Args:
            query: Search query
            collections: List of collection IDs to search
            limit: Maximum results per collection
        
        Returns:
            List of Hadith results
        """
        if collections is None:
            collections = ["eng-bukhari", "eng-muslim"]
        
        # Search all collections concurrently
        tasks = [
            self._search_collection(coll, query, limit)
            for coll in collections
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Flatten and filter results
        all_hadiths = []
        for result in results:
            if isinstance(result, list):
                all_hadiths.extend(result)
        
        return all_hadiths[:limit]
    
    async def _search_collection(
        self,
        collection: str,
        query: str,
        limit: int
    ) -> List[Dict]:
        """Search a specific Hadith collection"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/collections/{collection}/hadith",
                    params={"q": query, "limit": limit}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
                
                return []
                
        except Exception as e:
            logger.error(f"❌ Error searching {collection}: {e}")
            return []
    
    def get_collection_name(self, collection_id: str) -> str:
        """Get friendly collection name"""
        return self.collections.get(collection_id, collection_id)
