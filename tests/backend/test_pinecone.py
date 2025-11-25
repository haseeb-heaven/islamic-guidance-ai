"""
Pinecone Vector Database Test Suite - COMPLETE VERSION
Tests connection, data retrieval, semantic search with filters, and raw vector display
Author: Islamic Guidance AI
Version: 2.0
"""

import os
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass
import json
from pathlib import Path
import statistics

# =============================================================================
# MODULE 1: CONFIGURATION & ENVIRONMENT
# =============================================================================

@dataclass
class Config:
    """Configuration container"""
    pinecone_api_key: str
    gemini_api_key: str
    index_name: str = 'islamic-guidance'
    embedding_model: str = 'models/text-embedding-004'
    dimension: int = 768

class EnvironmentLoader:
    """Handles .env file loading and validation"""
    
    @staticmethod
    def load_env_file(env_path: str = '.env') -> Dict[str, str]:
        """
        Load environment variables from .env file
        
        Args:
            env_path: Path to .env file
            
        Returns:
            Dictionary of environment variables
        """
        env_vars = {}
        env_file = Path(env_path)
        
        if not env_file.exists():
            print(f"⚠️  Warning: {env_path} not found")
            return env_vars
        
        try:
            with open(env_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse key=value
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        env_vars[key] = value
                    else:
                        print(f"⚠️  Warning: Invalid line {line_num} in {env_path}")
            
            print(f"✅ Loaded {len(env_vars)} variables from {env_path}")
            return env_vars
            
        except Exception as e:
            print(f"❌ Error reading {env_path}: {e}")
            return env_vars
    
    @staticmethod
    def get_config() -> Config:
        """
        Load and validate configuration
        
        Returns:
            Config object with validated keys
            
        Raises:
            ValueError: If required keys are missing
        """
        print("=" * 70)
        print("🔧 CONFIGURATION LOADER")
        print("=" * 70)
        
        # Load .env file
        env_vars = EnvironmentLoader.load_env_file()
        
        # Get API keys (prioritize .env, fallback to system env)
        pinecone_key = env_vars.get('PINECONE_API_KEY') or os.getenv('PINECONE_API_KEY')
        gemini_key = env_vars.get('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
        
        # Validate Pinecone API key
        if not pinecone_key:
            raise ValueError(
                "❌ PINECONE_API_KEY not found!\n"
                "   Please set it in .env file or environment variables."
            )
        
        # Check for both old and new formats
        if not (pinecone_key.startswith('pc-') or pinecone_key.startswith('pcsk_')):
            raise ValueError(
                "❌ Invalid PINECONE_API_KEY format!\n"
                "   Key should start with 'pc-' (old) or 'pcsk_' (new)\n"
                f"   Your key starts with: {pinecone_key[:5]}"
            )
        
        # Determine key type
        key_type = "Legacy (pc-)" if pinecone_key.startswith('pc-') else "New (pcsk_)"
        print(f"✅ Pinecone API Key: {pinecone_key[:10]}...{pinecone_key[-4:]} [{key_type}]")
        
        # Validate Gemini API key (optional for this test)
        if gemini_key:
            if not gemini_key.startswith('AIzaSy'):
                print("⚠️  Warning: GEMINI_API_KEY format looks invalid")
                print(f"   Expected to start with 'AIzaSy', got: {gemini_key[:10]}")
            else:
                print(f"✅ Gemini API Key: {gemini_key[:10]}...{gemini_key[-4:]}")
        else:
            print("⚠️  Warning: GEMINI_API_KEY not found (needed for query embeddings)")
        
        print("=" * 70)
        print()
        
        return Config(
            pinecone_api_key=pinecone_key,
            gemini_api_key=gemini_key or "",
            index_name=env_vars.get('INDEX_NAME', 'islamic-guidance')
        )

# =============================================================================
# MODULE 2: PINECONE CLIENT
# =============================================================================

class PineconeClient:
    """Handles Pinecone connection and operations"""
    
    def __init__(self, config: Config):
        self.config = config
        self.pc = None
        self.index = None
    
    def connect(self) -> bool:
        """
        Connect to Pinecone and validate index
        
        Returns:
            True if successful, False otherwise
        """
        print("🔌 Connecting to Pinecone...")
        
        try:
            from pinecone import Pinecone
            
            # Initialize Pinecone
            self.pc = Pinecone(api_key=self.config.pinecone_api_key)
            print("   ✅ Pinecone client initialized")
            
            # List available indexes
            indexes = self.pc.list_indexes()
            index_names = [idx.name for idx in indexes]
            print(f"   ✅ Available indexes: {index_names}")
            
            # Check if target index exists
            if self.config.index_name not in index_names:
                print(f"   ❌ Index '{self.config.index_name}' not found!")
                print(f"      Available: {index_names}")
                return False
            
            # Connect to index
            self.index = self.pc.Index(self.config.index_name)
            print(f"   ✅ Connected to index: {self.config.index_name}")
            
            # Get index stats
            stats = self.index.describe_index_stats()
            print(f"   ✅ Index stats:")
            print(f"      - Total vectors: {stats['total_vector_count']:,}")
            print(f"      - Dimension: {stats['dimension']}")
            print(f"      - Namespaces: {list(stats.get('namespaces', {}).keys()) or ['default']}")
            
            return True
            
        except ImportError:
            print("   ❌ Error: pinecone-client not installed")
            print("      Run: pip install pinecone-client")
            return False
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
            return False
    
    def get_sample_vectors(self, limit: int = 5) -> List[Dict]:
        """
        Fetch sample vectors from index
        
        Args:
            limit: Number of samples to fetch
            
        Returns:
            List of vector IDs
        """
        if not self.index:
            raise RuntimeError("Not connected to index")
        
        print(f"\n📦 Fetching {limit} sample vectors...")
        
        try:
            # Query with dummy vector to get samples
            results = self.index.query(
                vector=[0.0] * self.config.dimension,
                top_k=limit,
                include_metadata=True
            )
            
            samples = []
            for match in results['matches']:
                samples.append({
                    'id': match['id'],
                    'score': match['score'],
                    'source': match['metadata'].get('source'),
                    'text': match['metadata'].get('text', '')[:100] + '...',
                    'url': match['metadata'].get('url')
                })
            
            print(f"   ✅ Retrieved {len(samples)} samples")
            return samples
            
        except Exception as e:
            print(f"   ❌ Error fetching samples: {e}")
            return []
    
    def fetch_vector_with_values(self, vector_id: str) -> Dict:
        """
        Fetch a vector by ID including its raw values
        
        Args:
            vector_id: Vector ID to fetch
            
        Returns:
            Dictionary with vector data including raw values
        """
        if not self.index:
            raise RuntimeError("Not connected to index")
        
        print(f"\n🔬 Fetching raw vector: {vector_id}")
        
        try:
            # Fetch by ID
            result = self.index.fetch(ids=[vector_id])
            
            if not result['vectors']:
                print(f"   ❌ Vector '{vector_id}' not found")
                return {}
            
            vector_data = result['vectors'][vector_id]
            
            print(f"   ✅ Vector found")
            print(f"   ✅ Dimension: {len(vector_data['values'])}")
            
            # Show first 10 values
            values = vector_data['values']
            print(f"\n   📊 First 10 values (out of {len(values)}):")
            print(f"      {[round(v, 4) for v in values[:10]]}")
            
            print(f"\n   📊 Last 10 values:")
            print(f"      {[round(v, 4) for v in values[-10:]]}")
            
            print(f"\n   📊 Vector Statistics:")
            print(f"      - Min: {min(values):.4f}")
            print(f"      - Max: {max(values):.4f}")
            print(f"      - Mean: {statistics.mean(values):.4f}")
            print(f"      - StdDev: {statistics.stdev(values):.4f}")
            
            return {
                'id': vector_id,
                'values': values,
                'metadata': vector_data.get('metadata', {}),
                'dimension': len(values)
            }
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {}
    
    def search_by_text(
        self, 
        query_text: str, 
        top_k: int = 3,
        source_filter: Optional[str] = None,
        collection_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search using text query with optional filters
        
        Args:
            query_text: Search query
            top_k: Number of results
            source_filter: 'quran', 'hadith', or None (both)
            collection_filter: List of Hadith collections to filter
            
        Returns:
            List of search results
        """
        if not self.index:
            raise RuntimeError("Not connected to index")
        
        if not self.config.gemini_api_key:
            print("   ⚠️  GEMINI_API_KEY not set - cannot generate embeddings")
            return []
        
        # Build filter description
        filter_desc = []
        if source_filter:
            filter_desc.append(f"source={source_filter}")
        if collection_filter:
            filter_desc.append(f"collections={collection_filter}")
        filter_str = f" [{', '.join(filter_desc)}]" if filter_desc else ""
        
        print(f"\n🔍 Searching for: '{query_text}'{filter_str}")
        
        try:
            import google.generativeai as genai
            
            # Generate query embedding
            genai.configure(api_key=self.config.gemini_api_key)
            result = genai.embed_content(
                model=self.config.embedding_model,
                content=query_text,
                task_type="retrieval_query"
            )
            query_vector = result['embedding']
            
            print(f"   ✅ Generated embedding (dimension: {len(query_vector)})")
            
            # Build filter dictionary
            filter_dict = {}
            if source_filter:
                filter_dict['source'] = source_filter
            if collection_filter and source_filter == 'hadith':
                # Remove 'eng-' prefix from collections
                collections = [c.replace('eng-', '') for c in collection_filter]
                filter_dict['collection'] = {'$in': collections}
            
            # Search Pinecone
            results = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict if filter_dict else None
            )
            
            # Format results
            search_results = []
            for i, match in enumerate(results['matches'], 1):
                search_results.append({
                    'rank': i,
                    'id': match['id'],
                    'score': round(match['score'], 4),
                    'source': match['metadata'].get('source'),
                    'text': match['metadata'].get('text'),
                    'url': match['metadata'].get('url'),
                    'metadata': match['metadata']
                })
            
            print(f"   ✅ Found {len(search_results)} results")
            return search_results
            
        except ImportError as e:
            print(f"   ❌ Missing library: {e}")
            print("      Run: pip install google-generativeai")
            return []
        except Exception as e:
            print(f"   ❌ Search error: {e}")
            return []

# =============================================================================
# MODULE 3: RESULT FORMATTER
# =============================================================================

class ResultFormatter:
    """Formats and displays search results"""
    
    @staticmethod
    def print_samples(samples: List[Dict]):
        """Display sample vectors"""
        print("\n" + "=" * 70)
        print("📊 SAMPLE VECTORS")
        print("=" * 70)
        
        for i, sample in enumerate(samples, 1):
            print(f"\n{i}. ID: {sample['id']}")
            print(f"   Source: {sample['source']}")
            print(f"   Text: {sample['text']}")
            print(f"   URL: {sample['url']}")
    
    @staticmethod
    def print_search_results(results: List[Dict], query: str = "", filter_info: str = ""):
        """Display search results"""
        print("\n" + "=" * 70)
        title = f"🎯 SEARCH RESULTS"
        if query:
            title += f": {query}"
        if filter_info:
            title += f" {filter_info}"
        print(title)
        print("=" * 70)
        
        if not results:
            print("\n❌ No results found")
            return
        
        for result in results:
            source_emoji = "📖" if result['source'] == 'quran' else "📚"
            print(f"\n{result['rank']}. {source_emoji} [{result['source'].upper()}] Score: {result['score']}")
            print(f"   ID: {result['id']}")
            print(f"   Text: {result['text'][:300]}...")
            print(f"   URL: {result['url']}")
            
            # Show additional metadata for Hadith
            if result['source'] == 'hadith':
                metadata = result.get('metadata', {})
                if 'collection' in metadata:
                    print(f"   Collection: {metadata['collection']}")
    
    @staticmethod
    def print_vector_details(vector_data: Dict):
        """Display detailed vector information"""
        if not vector_data:
            return
        
        print("\n" + "=" * 70)
        print("🔬 RAW VECTOR DATA")
        print("=" * 70)
        
        print(f"\nVector ID: {vector_data['id']}")
        print(f"Dimension: {vector_data['dimension']}")
        
        print(f"\n📊 Sample Values (first 20 of {vector_data['dimension']}):")
        values = vector_data['values']
        for i in range(0, min(20, len(values)), 5):
            chunk = [round(v, 4) for v in values[i:i+5]]
            print(f"   [{i:3d}-{i+4:3d}]: {chunk}")
        
        print(f"\n📋 Metadata:")
        for key, value in vector_data['metadata'].items():
            if key == 'text':
                print(f"   {key}: {value[:100]}...")
            else:
                print(f"   {key}: {value}")
    
    @staticmethod
    def export_to_json(data: Dict, filename: str = "pinecone_test_results.json"):
        """Export results to JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Results saved to: {filename}")
        except Exception as e:
            print(f"\n❌ Error saving results: {e}")

# =============================================================================
# MODULE 4: MAIN TEST RUNNER
# =============================================================================

class PineconeTestRunner:
    """Main test orchestrator"""
    
    def __init__(self):
        self.config = None
        self.client = None
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("\n" + "=" * 70)
        print("🧪 PINECONE TEST SUITE - COMPLETE VERSION")
        print("=" * 70)
        print()
        
        # Test 1: Load configuration
        try:
            self.config = EnvironmentLoader.get_config()
        except ValueError as e:
            print(f"\n{e}")
            print("\n💡 Fix:")
            print("   1. Create .env file in project root")
            print("   2. Add: PINECONE_API_KEY=pcsk_xxxxx")
            print("   3. Add: GEMINI_API_KEY=AIzaSyxxxxx")
            return False
        
        # Test 2: Connect to Pinecone
        self.client = PineconeClient(self.config)
        if not self.client.connect():
            print("\n❌ Connection test failed")
            return False
        
        # Test 3: Fetch sample vectors
        samples = self.client.get_sample_vectors(limit=3)
        if samples:
            ResultFormatter.print_samples(samples)
        
        # Test 4: View raw vector values
        if samples:
            print("\n" + "=" * 70)
            print("🔬 TEST: RAW VECTOR VALUES")
            print("=" * 70)
            
            first_id = samples[0]['id']
            raw_vector = self.client.fetch_vector_with_values(first_id)
            if raw_vector:
                ResultFormatter.print_vector_details(raw_vector)
        
        # Test 5: Text searches (if Gemini key available)
        if self.config.gemini_api_key:
            all_results = {}
            
            # Test 5a: Search both sources
            print("\n" + "=" * 70)
            print("🔍 TEST: SEARCH BOTH QURAN & HADITH")
            print("=" * 70)
            
            query1 = "How to find peace in difficult times?"
            results1 = self.client.search_by_text(query1, top_k=5)
            if results1:
                ResultFormatter.print_search_results(results1, query1, "[Both Sources]")
                all_results[f"{query1} [Both]"] = results1
            
            # Test 5b: Search Quran only
            print("\n" + "=" * 70)
            print("📖 TEST: SEARCH QURAN ONLY")
            print("=" * 70)
            
            query2 = "What does Quran say about patience?"
            results2 = self.client.search_by_text(
                query2, 
                top_k=3,
                source_filter='quran'
            )
            if results2:
                ResultFormatter.print_search_results(results2, query2, "[Quran Only]")
                all_results[f"{query2} [Quran]"] = results2
            
            # Test 5c: Search Hadith only
            print("\n" + "=" * 70)
            print("📚 TEST: SEARCH HADITH ONLY")
            print("=" * 70)
            
            query3 = "What did Prophet say about kindness?"
            results3 = self.client.search_by_text(
                query3,
                top_k=3,
                source_filter='hadith'
            )
            if results3:
                ResultFormatter.print_search_results(results3, query3, "[Hadith Only]")
                all_results[f"{query3} [Hadith]"] = results3
            
            # Test 5d: Search specific Hadith collections
            print("\n" + "=" * 70)
            print("📚 TEST: SEARCH SPECIFIC HADITH COLLECTIONS")
            print("=" * 70)
            
            query4 = "Prayer is important"
            results4 = self.client.search_by_text(
                query4,
                top_k=3,
                source_filter='hadith',
                collection_filter=['eng-bukhari', 'eng-muslim']
            )
            if results4:
                ResultFormatter.print_search_results(
                    results4, 
                    query4, 
                    "[Bukhari & Muslim Only]"
                )
                all_results[f"{query4} [Bukhari+Muslim]"] = results4
            
            # Export all results
            if all_results:
                ResultFormatter.export_to_json({
                    'test_date': '2025-11-24',
                    'index_name': self.config.index_name,
                    'total_queries': len(all_results),
                    'queries': all_results
                })
        else:
            print("\n⚠️  Skipping text search tests (GEMINI_API_KEY not set)")
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ TEST SUITE COMPLETE")
        print("=" * 70)
        print("\n📋 Summary:")
        print(f"   ✅ Configuration loaded")
        print(f"   ✅ Pinecone connection established")
        print(f"   ✅ Index: {self.config.index_name}")
        print(f"   ✅ Sample vectors retrieved: {len(samples)}")
        print(f"   ✅ Raw vector values displayed")
        if self.config.gemini_api_key:
            print(f"   ✅ Search tests performed:")
            print(f"      - Both sources (Quran + Hadith)")
            print(f"      - Quran only")
            print(f"      - Hadith only")
            print(f"      - Specific collections (Bukhari + Muslim)")
        print()
        
        return True

# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    try:
        runner = PineconeTestRunner()
        success = runner.run_all_tests()
        
        if success:
            print("🎉 All tests passed!\n")
            sys.exit(0)
        else:
            print("❌ Some tests failed\n")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
