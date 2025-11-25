"""
Vector Search Service using Pinecone
"""

import os
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    from pinecone import Pinecone
except ImportError:
    Pinecone = None

@dataclass
class VectorConfig:
    """Vector search configuration"""
    pinecone_api_key: str
    index_name: str = 'islamic-guidance'
    embedding_model: str = 'llama-text-embed-v2'
    default_results: int = 3

class SearchEngine:
    """Handles vector search operations using Pinecone Inference"""
    
    def __init__(self):
        self.api_key = os.getenv('PINECONE_API_KEY')
        self.index_name = os.getenv('INDEX_NAME', 'islamic-guidance')
        self.embedding_model = 'llama-text-embed-v2'
        self.pc = None
        self.index = None
        self._connected = False
        
        if not self.api_key:
            print("[WARNING] PINECONE_API_KEY not found in environment variables", file=sys.stderr)

    def connect(self) -> bool:
        """Connect to Pinecone"""
        if self._connected:
            return True
            
        if not self.api_key:
            return False

        try:
            if Pinecone is None:
                print("[ERROR] Pinecone library not installed", file=sys.stderr)
                return False
                
            # Connect to Pinecone
            self.pc = Pinecone(api_key=self.api_key)
            self.index = self.pc.Index(self.index_name)
            self._connected = True
            print(f"[SUCCESS] Connected to Pinecone index: {self.index_name}", file=sys.stdout)
            return True
            
        except Exception as e:
            print(f"[ERROR] Pinecone connection error: {e}", file=sys.stderr)
            return False

    def search(self, query: str, source_filter: Optional[str] = None, 
              collection_filter: Optional[List[str]] = None, top_k: int = 3,
              score_threshold: float = 0.0) -> List[Dict]:
        """Search vector database using Pinecone Inference"""
        if not self.connect():
            return []

        try:
            # 1. Generate Query Embedding using Pinecone Inference
            embedding_response = self.pc.inference.embed(
                model=self.embedding_model,
                inputs=[query],
                parameters={"input_type": "query"}
            )
            query_vector = embedding_response[0]['values']

            # 2. Build Metadata Filters
            filter_dict = {}
            if source_filter and source_filter != 'both':
                filter_dict['source'] = source_filter
            
            if collection_filter and source_filter == 'hadith':
                # Clean up collection names (remove 'eng-' prefix if present)
                collections = [c.replace('eng-', '') for c in collection_filter]
                if collections:
                    filter_dict['collection'] = {'$in': collections}

            # 3. Search Index
            results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict if filter_dict else None
            )

            # 4. Format Results
            formatted = []
            for i, match in enumerate(results['matches'], 1):
                score = match['score']
                if score < score_threshold:
                    continue
                    
                formatted.append({
                    'rank': i,
                    'score': round(score, 4),
                    'source': match['metadata'].get('source', 'Unknown'),
                    'text': match['metadata'].get('text', 'No text available'),
                    'url': match['metadata'].get('url', '#'),
                    'collection': match['metadata'].get('collection', 'N/A')
                })
            
            return formatted

        except Exception as e:
            print(f"[ERROR] Vector search error: {e}", file=sys.stderr)
            return []
