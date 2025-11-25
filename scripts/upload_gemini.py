"""
Upload to islamic-guidance-gemini index using Gemini embeddings
Run ONCE on Google Colab with T4 GPU
Backend will use same Gemini API for queries (Vercel compatible)

UPDATED:
- Corrected Gemini model name to 'models/text-embedding-004'
- Corrected dimension to 768
- Added filtering for empty text strings to prevent API errors
"""

import os
import json
import time
import pickle
import argparse
from pathlib import Path
from tqdm import tqdm
from pinecone import Pinecone, ServerlessSpec
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("./data")
QURAN_FILE = DATA_DIR / "quran.json"
HADITH_DIR = DATA_DIR / "hadith"
INDEX_NAME = "islamic-guidance-gemini"

# ✅ FIXED: Correct Gemini model name and dimension
EMBEDDING_MODEL = "gemini-embedding-001"
DIMENSION = 3072
BATCH_SIZE = 100

print(f"🎯 Using Gemini Embeddings: {EMBEDDING_MODEL}")
print(f"📦 Target Index: {INDEX_NAME}")
print()

def load_quran_data():
    if not QURAN_FILE.exists():
        raise FileNotFoundError("Quran JSON not found. Please run download_data.py first.")
    with open(QURAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)['data']['surahs']

def load_hadith_data():
    hadiths = []
    if not HADITH_DIR.exists():
        raise FileNotFoundError("Hadith directory not found. Please run download_data.py first.")
    for filepath in HADITH_DIR.glob("*.json"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            hadiths.extend(data.get('hadiths', []))
    return hadiths

def parse_quran_verses(data):
    verses = []
    for surah in data:
        for ayah in surah['ayahs']:
            # ✅ ADDED: Filter out empty text strings to prevent errors
            text = ayah['text'].strip()
            if not text:
                continue

            verses.append({
                "id": f"quran_{surah['number']}_{ayah['numberInSurah']}",
                "text": text,
                "source": "quran",
                "surah": surah['number'],
                "ayah": ayah['numberInSurah'],
                "surah_name": surah['englishName'],
                "metadata": {
                    "source": "quran",
                    "surah": str(surah['number']),
                    "ayah": str(ayah['numberInSurah']),
                    "surah_name": surah['englishName'],
                    "url": f"https://quran.com/{surah['number']}:{ayah['numberInSurah']}"
                }
            })
    return verses

def parse_hadiths(data):
    parsed = []
    for h in data:
        # ✅ ADDED: Filter out empty text strings to prevent errors
        text = h.get('text', '').strip()
        if not text:
            continue

        collection = h.get('collection', 'unknown')
        number = h.get('hadithnumber', '0')
        parsed.append({
            "id": f"hadith_{collection}_{number}",
            "text": text,
            "source": "hadith",
            "collection": collection,
            "number": number,
            "metadata": {
                "source": "hadith",
                "collection": collection,
                "number": str(number),
                "url": f"https://sunnah.com/{collection}:{number}"
            }
        })
    return parsed

class GeminiEmbeddingGenerator:
    """Generate embeddings using Gemini API (Vercel compatible)"""
    
    def __init__(self, api_key: str):
        print("=" * 70)
        print("🧠 INITIALIZING GEMINI EMBEDDINGS")
        print("=" * 70)
        
        genai.configure(api_key=api_key)
        self.model = EMBEDDING_MODEL
        self.dimension = DIMENSION
        
        print(f"✅ Model: {self.model}")
        print(f"✅ Dimension: {self.dimension}")
        print("=" * 70)
        print()
    
    def generate_batch(self, texts: list, batch_size: int = 100):
        """Generate embeddings in batches"""
        print(f"🔄 Generating {len(texts):,} embeddings...")
        print(f"   Batch Size: {batch_size}")
        print()
        
        embeddings = []
        
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
            batch = texts[i:i+batch_size]
            
            try:
                result = genai.embed_content(
                    model=self.model,
                    content=batch,
                    task_type="RETRIEVAL_DOCUMENT"
                )
                
                if isinstance(result['embedding'][0], list):
                    embeddings.extend(result['embedding'])
                else:
                    embeddings.append(result['embedding'])
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"\n❌ Batch {i} error: {e}")
                print(f"   Retrying individually...")
                
                for text in batch:
                    try:
                        result = genai.embed_content(
                            model=self.model,
                            content=text,
                            task_type="retrieval_document"
                        )
                        embeddings.append(result['embedding'])
                        time.sleep(0.05)
                    except Exception as e2:
                        print(f"   ⚠️  Failed: {text[:50]}... - Adding zero vector")
                        embeddings.append([0.0] * self.dimension)
        
        print(f"\n✅ Generated {len(embeddings):,} embeddings")
        return embeddings

class PineconeUploader:
    def __init__(self, api_key: str, index_name: str, dimension: int = DIMENSION):
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        self.index = None

    def create_or_connect_index(self):
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if self.index_name in existing_indexes:
            print(f"✅ Connecting to: {self.index_name}")
        else:
            print(f"🔨 Creating index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
            time.sleep(10)
        
        self.index = self.pc.Index(self.index_name)

    def upload_batch(self, data: list, embeddings, batch_size: int = BATCH_SIZE):
        if not self.index:
            raise ValueError("Index not initialized")
        
        print(f"\n☁️  Uploading {len(data):,} vectors...")
        
        vectors = []
        for item, embedding in zip(data, embeddings):
            vector = {
                'id': item['id'],
                'values': embedding if isinstance(embedding, list) else embedding.tolist(),
                'metadata': {
                    'text': item['text'][:1000],
                    'source': item['source'],
                    'url': item['metadata']['url'],
                    **(
                        {
                            'surah': str(item['surah']),
                            'ayah': str(item['ayah']),
                            'surah_name': item['surah_name']
                        } if item['source'] == 'quran' else {
                            'collection': item['collection'],
                            'number': str(item['number'])
                        }
                    )
                }
            }
            vectors.append(vector)
        
        total = 0
        pbar = tqdm(total=len(vectors), desc="Uploading", unit="vectors")
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i+batch_size]
            try:
                self.index.upsert(vectors=batch)
                total += len(batch)
                pbar.update(len(batch))
            except Exception as e:
                print(f"\n❌ Batch {i} error: {e}")
        
        pbar.close()
        print(f"\n✅ Uploaded {total:,} vectors")
        return total

def main():
    parser = argparse.ArgumentParser(description="Upload with Gemini embeddings")
    parser.add_argument("--pinecone_key", type=str, required=False)
    parser.add_argument("--gemini_key", type=str, required=False)
    args = parser.parse_args()

    if not args.pinecone_key:
        args.pinecone_key = os.getenv("PINECONE_API_KEY")
    if not args.gemini_key:
        args.gemini_key = os.getenv("GEMINI_API_KEY")
    
    if not args.pinecone_key or not args.gemini_key:
        raise ValueError("API keys not found. Please set them in your .env file or pass them as arguments.")
    
    print("=" * 70)
    print("📥 LOADING DATA")
    print("=" * 70)
    
    quran_raw = load_quran_data()
    hadith_raw = load_hadith_data()
    
    quran = parse_quran_verses(quran_raw)
    hadith = parse_hadiths(hadith_raw)
    
    combined = quran + hadith
    print(f"✅ Total valid items: {len(combined):,}")
    print()
    
    # Generate embeddings with Gemini
    generator = GeminiEmbeddingGenerator(args.gemini_key)
    texts = [item['text'] for item in combined]
    embeddings = generator.generate_batch(texts, batch_size=100)
    
    # Save embeddings
    print("\n💾 Saving embeddings...")
    with open("gemini_embeddings.pkl", "wb") as f:
        pickle.dump({
            'embeddings': embeddings,
            'metadata': combined,
            'model': EMBEDDING_MODEL,
            'dimension': DIMENSION
        }, f)
    print("✅ Saved to gemini_embeddings.pkl")
    
    # Upload to Pinecone
    print("\n" + "=" * 70)
    print("☁️  UPLOADING TO PINECONE")
    print("=" * 70)
    
    uploader = PineconeUploader(args.pinecone_key, INDEX_NAME, dimension=generator.dimension)
    uploader.create_or_connect_index()
    total = uploader.upload_batch(combined, embeddings)
    
    print("\n" + "=" * 70)
    print("🎉 COMPLETE!")
    print("=" * 70)
    print(f"✅ Index: {INDEX_NAME}")
    print(f"✅ Vectors: {total:,}")
    print(f"✅ Model: {EMBEDDING_MODEL}")
    print(f"✅ Dimension: {DIMENSION}")
    print()

if __name__ == "__main__":
    main()
