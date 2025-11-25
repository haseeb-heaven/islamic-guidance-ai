"""
Vector Search Service using Pinecone
Lightweight - NO heavy ML models (Vercel compatible)
Uses Gemini API for query embeddings
"""

import os
import sys
from typing import List, Dict, Optional
from pinecone import Pinecone
import google.generativeai as genai
import asyncio

# Import cache
try:
    from backend.cache import cache
except ImportError:
    try:
        from cache import cache
    except ImportError:
        class MockCache:
            async def get(self, k): return None
            async def set(self, k, v, t=0): pass
        cache = MockCache()

# =============================================================================
# CONFIGURATION
# =============================================================================
INDEX_NAME = 'islamic-guidance'
EMBEDDING_MODEL = 'models/text-embedding-004'
EMBEDDING_DIMENSION = 768

# Global connection cache
_pinecone_index = None

# =============================================================================
# PINECONE CONNECTION
# =============================================================================
def get_pinecone_index():
    """
    Lazy load Pinecone index connection
    Cached globally per container (Vercel warm start)
    """
    global _pinecone_index
    
    if _pinecone_index is None:
        api_key = os.getenv('PINECONE_API_KEY')
        if not api_key:
            raise ValueError("PINECONE_API_KEY not set in environment")
        
        print("[VECTOR] Connecting to Pinecone...", file=sys.stdout, flush=True)
        
        try:
            pc = Pinecone(api_key=api_key)
            _pinecone_index = pc.Index(INDEX_NAME)
            print(f"[VECTOR] Connected to index: {INDEX_NAME}", file=sys.stdout, flush=True)
        except Exception as e:
            print(f"[VECTOR] Connection error: {e}", file=sys.stderr, flush=True)
            raise
    
    return _pinecone_index

# =============================================================================
# EMBEDDING GENERATION (Gemini API)
# =============================================================================
async def generate_query_embedding(query: str) -> List[float]:
    """
    Generate embedding using Gemini API
    Lightweight - no local ML models required
    
    Args:
        query: User's search query
    
    Returns:
        768-dimensional embedding vector
    """
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")
        
        genai.configure(api_key=api_key)
        
        # Generate embedding (optimized for search queries)
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=query,
            task_type="retrieval_query"
        )
        
        return result['embedding']
        
    except Exception as e:
        print(f"[VECTOR] Embedding error: {e}", file=sys.stderr, flush=True)
        raise

# =============================================================================
# SEMANTIC SEARCH
# =============================================================================
async def search_semantic_async(
    query: str,
    top_k: int = 5,
    source_filter: Optional[str] = None,
    collection_filter: Optional[List[str]] = None
) -> List[Dict]:
    """
    Semantic search using Pinecone vector database
    NO heavy ML models - uses Gemini API for embeddings
    
    Args:
        query: User's question
        top_k: Number of results to return
        source_filter: 'quran', 'hadith', or None (both)
        collection_filter: List of Hadith collections to filter
    
    Returns:
        List of relevant verses/hadiths with metadata
    """
    try:
        # Check cache first
        cache_key = f"semantic_v2:{query}:{top_k}:{source_filter}:{collection_filter}"
        cached_result = await cache.get(cache_key)
        if cached_result:
            print(f"[CACHE] Hit for semantic search", file=sys.stdout, flush=True)
            return cached_result
        
        print(f"[VECTOR] Semantic search: '{query[:50]}'", file=sys.stdout, flush=True)
        
        # Step 1: Generate query embedding (Gemini API)
        query_vector = await generate_query_embedding(query)
        
        # Step 2: Build filter dictionary
        filter_dict = {}
        
        if source_filter and source_filter != "both":
            filter_dict['source'] = source_filter
        
        if collection_filter and source_filter == 'hadith':
            # Remove 'eng-' prefix from collection names
            collections = [c.replace('eng-', '') for c in collection_filter]
            filter_dict['collection'] = {'$in': collections}
        
        # Step 3: Query Pinecone
        index = get_pinecone_index()
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict if filter_dict else None
        )
        
        # Step 4: Format results
        formatted_results = []
        for match in results['matches']:
            formatted_results.append({
                'id': match['id'],
                'score': round(match['score'], 4),
                'source': match['metadata']['source'],
                'text': match['metadata']['text'],
                'url': match['metadata']['url'],
                'metadata': match['metadata']
            })
        
        print(f"[VECTOR] Found {len(formatted_results)} results", file=sys.stdout, flush=True)
        
        # Cache results (1 hour TTL)
        try:
            await cache.set(cache_key, formatted_results, ttl=3600)
        except Exception as e:
            print(f"[CACHE] Error saving: {e}", file=sys.stderr, flush=True)
        
        return formatted_results
        
    except Exception as e:
        print(f"[VECTOR] Error: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc()
        return []

# =============================================================================
# SYNCHRONOUS WRAPPER
# =============================================================================
def search_semantic(query: str, top_k: int = 5, **kwargs) -> List[Dict]:
    """Synchronous wrapper for search_semantic_async"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(search_semantic_async(query, top_k, **kwargs))
