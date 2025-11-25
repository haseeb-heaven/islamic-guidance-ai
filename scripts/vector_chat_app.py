"""
Islamic Guidance AI - Interactive Chat Application
Search Quran & Hadith using Pinecone Vector Database (Integrated Inference)
Author: Islamic Guidance AI
Version: 2.0 (Pinecone Inference Edition)
"""

import os
import sys
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# MODULE 1: CONFIGURATION MANAGER
# =============================================================================

@dataclass
class AppConfig:
    """Application configuration"""
    pinecone_api_key: str
    index_name: str = 'islamic-guidance'
    embedding_model: str = 'llama-text-embed-v2'
    default_results: int = 3

class ConfigManager:
    """Manages application configuration"""
    
    @staticmethod
    def get_config() -> Optional[AppConfig]:
        """Load and validate configuration"""
        pinecone_key = os.getenv('PINECONE_API_KEY')
        
        if not pinecone_key:
            print("❌ Error: PINECONE_API_KEY not found in .env")
            return None

        return AppConfig(
            pinecone_api_key=pinecone_key,
            index_name=os.getenv('INDEX_NAME', 'islamic-guidance')
        )

# =============================================================================
# MODULE 2: SEARCH ENGINE (UPDATED FOR INFERENCE)
# =============================================================================

class SearchEngine:
    """Handles vector search operations using Pinecone Inference"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.index = None
        self.pc = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to Pinecone"""
        try:
            from pinecone import Pinecone
            
            # Connect to Pinecone
            self.pc = Pinecone(api_key=self.config.pinecone_api_key)
            self.index = self.pc.Index(self.config.index_name)
            self._connected = True
            return True
            
        except ImportError:
            print("❌ Error: Missing library. Run: pip install pinecone-client")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False

    def search(self, query: str, source_filter: Optional[str] = None, 
              collection_filter: Optional[List[str]] = None, top_k: int = 3) -> List[Dict]:
        """Search vector database using Pinecone Inference"""
        if not self._connected:
            return []

        try:
            # 1. Generate Query Embedding using Pinecone Inference
            # We use the SAME model as the index to ensure 1024 dimensions
            embedding_response = self.pc.inference.embed(
                model=self.config.embedding_model,
                inputs=[query],
                parameters={"input_type": "query"}
            )
            query_vector = embedding_response[0]['values']

            # 2. Build Metadata Filters
            filter_dict = {}
            if source_filter:
                filter_dict['source'] = source_filter
            
            if collection_filter and source_filter == 'hadith':
                # Clean up collection names (remove 'eng-' prefix if present)
                collections = [c.replace('eng-', '') for c in collection_filter]
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
                formatted.append({
                    'rank': i,
                    'score': round(match['score'], 4),
                    'source': match['metadata'].get('source', 'Unknown'),
                    'text': match['metadata'].get('text', 'No text available'),
                    'url': match['metadata'].get('url', '#'),
                    'collection': match['metadata'].get('collection', 'N/A')
                })
            
            return formatted

        except Exception as e:
            print(f"❌ Search error: {e}")
            return []

# =============================================================================
# MODULE 3: USER INTERFACE (Unchanged visuals)
# =============================================================================

class UserInterface:
    """Handles user interaction and display"""
    
    @staticmethod
    def clear_screen():
        os.system('cls' if os.name == 'nt' else 'clear')

    @staticmethod
    def print_header():
        UserInterface.clear_screen()
        print("=" * 70)
        print("🕌 ISLAMIC GUIDANCE AI - INTERACTIVE CHAT")
        print("=" * 70)
        print()

    @staticmethod
    def print_menu(current_source: str, current_collections: List[str]):
        print("\n" + "-" * 70)
        print("⚙️  CURRENT SETTINGS:")
        print(f"   📚 Source: {current_source.upper()}")
        if current_source == 'hadith' and current_collections:
            collections_str = ', '.join([c.replace('eng-', '').capitalize() for c in current_collections])
            print(f"   📖 Collections: {collections_str}")
            
        print("\n📋 MENU OPTIONS:")
        print("   [1] Search Quran only")
        print("   [2] Search Hadith only")
        print("   [3] Search Both (Quran + Hadith)")
        print("   [4] Select Hadith collections")
        print("   [5] Change number of results")
        print("   [6] Chat (Ask a question)")
        print("   [Q] Quit application")
        print("-" * 70)

    @staticmethod
    def print_results(results: List[Dict], query: str):
        MIN_SCORE = 0.50
        
        if not results:
            print("\n❌ No results found. Try rephrasing your question.")
            return

        print(f"\n🎯 RESULTS FOR: '{query}'")
        print("=" * 70)

        for result in results:
            quality_emoji = "✅" if result['score'] >= MIN_SCORE else "⚠️"
            source_emoji = "📖" if result['source'] == 'quran' else "📚"
            
            print(f"\n{quality_emoji} Result #{result['rank']} | Score: {result['score']:.4f}")
            print(f"   {source_emoji} Source: {result['source'].upper()}")
            
            if result['source'] == 'hadith':
                print(f"   Collection: {result['collection'].capitalize()}")
            
            # Truncate text nicely
            text = result['text']
            if len(text) > 200:
                text = text[:200] + "..."
            
            print(f"   Text: {text}")
            print(f"   URL:  {result['url']}")

    @staticmethod
    def get_input(prompt: str) -> str:
        try:
            return input(f"\n{prompt} ").strip()
        except (KeyboardInterrupt, EOFError):
            return 'Q'

    @staticmethod
    def show_loading(message: str = "Searching"):
        print(f"\n{message}", end='', flush=True)
        for _ in range(3):
            time.sleep(0.3)
            print(".", end='', flush=True)
        print()

# =============================================================================
# MODULE 4: APPLICATION CONTROLLER
# =============================================================================

class ChatApplication:
    """Main application controller"""
    
    HADITH_COLLECTIONS = [
        'eng-bukhari', 'eng-muslim', 'eng-abudawud', 
        'eng-tirmidhi', 'eng-nasai', 'eng-ibnmajah'
    ]

    def __init__(self, config: AppConfig):
        self.config = config
        self.search_engine = SearchEngine(config)
        self.ui = UserInterface()
        
        # State
        self.current_source = 'both'
        self.selected_collections = self.HADITH_COLLECTIONS.copy()
        self.num_results = config.default_results
        self.running = False

    def initialize(self) -> bool:
        self.ui.print_header()
        print("🔄 Initializing...")
        if not self.search_engine.connect():
            print("\n❌ Failed to connect to Pinecone")
            return False
        print("✅ Connected successfully!")
        time.sleep(1)
        return True

    def handle_menu_selection(self, choice: str) -> bool:
        choice = choice.upper()
        
        if choice == 'Q':
            return False
        elif choice == '1':
            self.current_source = 'quran'
            print("✅ Source set to: Quran only")
            time.sleep(1)
        elif choice == '2':
            self.current_source = 'hadith'
            print("✅ Source set to: Hadith only")
            time.sleep(1)
        elif choice == '3':
            self.current_source = 'both'
            print("✅ Source set to: Both (Quran + Hadith)")
            time.sleep(1)
        elif choice == '4':
            self.select_collections()
        elif choice == '5':
            self.change_num_results()
        elif choice == '6':
            query = self.ui.get_input("💬 Ask your question:")
            if query:
                self.process_query(query)
        else:
            # Treat number/invalid inputs as potential queries if not strictly matching options
            # But for this menu logic, strict is better. 
            # However, user might type "prayer" directly.
            # Let's keep strict menu for clarity, or forward to search.
            print("⚠️ Invalid option. Try 1-6 or Q.")
            time.sleep(1)
            
        return True

    def select_collections(self):
        self.ui.clear_screen()
        print("=" * 70)
        print("📚 SELECT HADITH COLLECTIONS")
        print("=" * 70)
        
        for i, collection in enumerate(self.HADITH_COLLECTIONS, 1):
            name = collection.replace('eng-', '').capitalize()
            selected = "✓" if collection in self.selected_collections else " "
            print(f" [{i}] [{selected}] {name}")
            
        print("\nInstructions:")
        print(" - Enter numbers (e.g., '1 3')")
        print(" - Enter 'all' for all collections")
        print(" - Press Enter to keep current")
        
        choice = self.ui.get_input("Your choice:")
        if not choice: return

        if choice.lower() == 'all':
            self.selected_collections = self.HADITH_COLLECTIONS.copy()
            print("✅ All collections selected")
        else:
            try:
                indices = [int(x) - 1 for x in choice.split()]
                new_selection = [
                    self.HADITH_COLLECTIONS[i] 
                    for i in indices 
                    if 0 <= i < len(self.HADITH_COLLECTIONS)
                ]
                if new_selection:
                    self.selected_collections = new_selection
                    names = [c.replace('eng-', '').capitalize() for c in new_selection]
                    print(f"✅ Selected: {', '.join(names)}")
                else:
                    print("⚠️ No valid selection.")
            except ValueError:
                print("⚠️ Invalid input.")
        time.sleep(1.5)

    def change_num_results(self):
        print(f"\n📊 Current limit: {self.num_results}")
        choice = self.ui.get_input("Enter new number (1-20):")
        if not choice: return
        try:
            num = int(choice)
            if 1 <= num <= 20:
                self.num_results = num
                print(f"✅ Results limit set to: {num}")
            else:
                print("⚠️ Enter number between 1-20")
        except ValueError:
            print("⚠️ Invalid number")
        time.sleep(1)

    def process_query(self, query: str):
        if not query: return
        self.ui.show_loading("🔍 Searching Pinecone")
        
        source_filter = None if self.current_source == 'both' else self.current_source
        collection_filter = self.selected_collections if self.current_source == 'hadith' else None
        
        results = self.search_engine.search(
            query=query,
            source_filter=source_filter,
            collection_filter=collection_filter,
            top_k=self.num_results
        )
        
        self.ui.print_results(results, query)
        input("\n📌 Press Enter to continue...")

    def run(self):
        if not self.initialize(): return
        self.running = True
        while self.running:
            try:
                self.ui.print_header()
                self.ui.print_menu(self.current_source, self.selected_collections)
                choice = self.ui.get_input("Enter option:")
                
                # Treat input as search if it's not a menu command (heuristic)
                if len(choice) > 2:
                    self.process_query(choice)
                else:
                    if not self.handle_menu_selection(choice):
                        break
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                input("Press Enter...")
        
        self.ui.clear_screen()
        print("\n👋 Ma'as-salama! (Goodbye)")

# =============================================================================
# MAIN
# =============================================================================

def main():
    try:
        config = ConfigManager.get_config()
        if not config:
            print("\n💡 Setup: Add PINECONE_API_KEY to .env file")
            sys.exit(1)
            
        app = ChatApplication(config)
        app.run()
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
