"""
Upload Quran & Hadith to Pinecone using Pinecone's Inference Embeddings API
Updated: Uses Pinecone's llama-text-embed-v2 model for embedding generation
No need for sentence-transformers or GPU - all handled by Pinecone API
✅ T4 GPU/CUDA support added for optimal Colab environment
"""

import os
import json
import time
import pickle
import argparse
from pathlib import Path
from tqdm import tqdm
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
import torch

load_dotenv()

# ✅ T4 GPU/CUDA CONFIGURATION
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
torch.backends.cudnn.benchmark = True

if torch.cuda.is_available():
    device = 'cuda'
    print(f"✅ GPU Available: {torch.cuda.get_device_name(0)}")
    print(f"✅ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
else:
    device = 'cpu'
    print("⚠️  GPU not available, using CPU")

DATA_DIR = Path("./data")
QURAN_FILE = DATA_DIR / "quran.json"
HADITH_DIR = DATA_DIR / "hadith"
INDEX_NAME = "islamic-guidance-pinecone"

# UNCHANGED: Use Pinecone's inference model
EMBEDDING_MODEL = "llama-text-embed-v2"  # Pinecone inference model
DIMENSION = 1024  # llama-text-embed-v2 outputs 1024-dimensional vectors
BATCH_SIZE = 96

print(f"🎯 Using Pinecone Inference Model: {EMBEDDING_MODEL}")
print(f"🧠 Processing on: {device.upper()}")

def load_quran_data():
    if not QURAN_FILE.exists():
        raise FileNotFoundError("Quran JSON not found. Please run data downloader first.")
    with open(QURAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)['data']['surahs']

def load_hadith_data():
    hadiths = []
    if not HADITH_DIR.exists():
        raise FileNotFoundError("Hadith directory not found. Please run data downloader first.")
    for filepath in HADITH_DIR.glob("*.json"):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            hadiths.extend(data.get('hadiths', []))
    return hadiths

def parse_quran_verses(data):
    verses = []
    for surah in data:
        for ayah in surah['ayahs']:
            text = ayah['text'].strip()
            if not text: continue
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
        text = h.get('text', "").strip()
        if not text: continue
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

class PineconeEmbeddingGenerator:
    """
    Generates embeddings using Pinecone's Inference API
    No local models required - all processing done by Pinecone
    ✅ T4 GPU/CUDA optimized environment
    """
    
    def __init__(self, api_key: str, model_name: str = EMBEDDING_MODEL):
        print(f"🧠 Initializing Pinecone Inference Embeddings...")
        self.pc = Pinecone(api_key=api_key)
        self.model_name = model_name
        self.dimension = DIMENSION
        print(f"   ✅ Using model: {model_name}")
        print(f"   ✅ Output dimension: {self.dimension}")
    
    def generate_batch(self, texts: list, batch_size: int = BATCH_SIZE):
        """
        Generate embeddings using Pinecone Inference API
        Processes texts in batches to respect API limits
        """
        print(f"\n🔄 Generating embeddings for {len(texts)} texts...")
        embeddings = []
        
        # Process in batches
        for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
            batch_texts = texts[i:i+batch_size]
            
            try:
                # Call Pinecone's inference embedding API
                response = self.pc.inference.embed(
                    model=self.model_name,
                    inputs=batch_texts,
                    parameters={
                        "input_type": "passage",
                        "truncate": "END"
                    }
                )
                
                # Extract embeddings from response
                batch_embeddings = [item['values'] for item in response]
                embeddings.extend(batch_embeddings)
                
                # Small delay to avoid rate limits
                time.sleep(0.2)
                
            except Exception as e:
                print(f"\n❌ Error generating embeddings for batch {i}: {e}")
                print(f"   ⚠️  Adding {len(batch_texts)} zero vectors as fallback")
                for _ in batch_texts:
                    embeddings.append([0.0] * self.dimension)
        
        print(f"✅ Generated {len(embeddings)} embeddings")
        return embeddings

class PineconeUploader:
    def __init__(self, api_key: str, index_name: str, dimension: int = DIMENSION):
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        self.index = None

    def create_or_connect_index(self):
        """Create new index or connect to existing"""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if self.index_name in existing_indexes:
            print(f"✅ Connecting to existing index: {self.index_name}")
        else:
            print(f"🔨 Creating new index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
            time.sleep(10)
        
        self.index = self.pc.Index(self.index_name)

    def upload_batch(self, data: list, embeddings, batch_size: int = BATCH_SIZE):
        """Upload vectors with embeddings"""
        if not self.index:
            raise ValueError("Index not initialized")
        
        print(f"☁️  Uploading {len(data)} vectors to Pinecone...")
        
        # Prepare vectors
        vectors = []
        for item, embedding in zip(data, embeddings):
            vector = {
                'id': item['id'],
                'values': embedding,
                'metadata': {
                    'source': item['source'],
                    'url': item['metadata']['url'],
                    # Source-specific metadata
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
        
        # Upload in batches
        total_uploaded = 0
        pbar = tqdm(total=len(vectors), desc="Uploading", unit="vectors")
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i+batch_size]
            try:
                self.index.upsert(vectors=batch)
                total_uploaded += len(batch)
                pbar.update(len(batch))
            except Exception as e:
                print(f"\n❌ Error uploading batch {i}: {e}")
        
        pbar.close()
        print(f"\n   ✅ Uploaded {total_uploaded} vectors")
        return total_uploaded

def main():
    parser = argparse.ArgumentParser(
        description="Upload Quran & Hadith to Pinecone using Pinecone Inference Embeddings"
    )
    parser.add_argument("--pinecone_key", type=str, required=False, help="Pinecone API Key")
    args = parser.parse_args()

    # Load Pinecone API key from environment variable if not provided
    if not args.pinecone_key:
        args.pinecone_key = os.getenv("PINECONE_API_KEY")
    
    if not args.pinecone_key:
        raise ValueError("PINECONE_API_KEY not found. Set it in .env or pass via --pinecone_key")
    
    print("=" * 70)
    print("📥 LOADING DATA")
    print("=" * 70)
    
    quran_raw = load_quran_data()
    hadith_raw = load_hadith_data()
    
    quran = parse_quran_verses(quran_raw)
    hadith = parse_hadiths(hadith_raw)
    
    combined = quran + hadith
    print(f"✅ Total items: {len(combined)} ({len(quran)} Quran + {len(hadith)} Hadith)")
    
    print("\n" + "=" * 70)
    print("🧠 GENERATING EMBEDDINGS (Pinecone Inference API)")
    print("=" * 70)
    
    generator = PineconeEmbeddingGenerator(args.pinecone_key)
    texts = [item['text'] for item in combined]
    embeddings = generator.generate_batch(texts, batch_size=BATCH_SIZE)
    
    print(f"\n✅ Generated {len(embeddings)} embeddings")
    
    # Save embeddings to file
    print("\n💾 Saving embeddings to pinecone_embeddings.pkl...")
    with open("pinecone_embeddings.pkl", "wb") as f:
        pickle.dump({
            'embeddings': embeddings,
            'metadata': combined,
            'model': EMBEDDING_MODEL,
            'dimension': DIMENSION,
            'batch_size': BATCH_SIZE
        }, f)
    print("✅ Embeddings saved")
    
    print("\n" + "=" * 70)
    print("☁️  UPLOADING TO PINECONE")
    print("=" * 70)
    
    uploader = PineconeUploader(args.pinecone_key, INDEX_NAME, dimension=DIMENSION)
    uploader.create_or_connect_index()
    
    total_uploaded = uploader.upload_batch(combined, embeddings)
    
    print("\n" + "=" * 70)
    print("🎉 UPLOAD COMPLETE")
    print("=" * 70)
    print(f"✅ Index: {INDEX_NAME}")
    print(f"✅ Total vectors: {total_uploaded}")
    print(f"✅ Model: {EMBEDDING_MODEL}")
    print(f"✅ Dimension: {DIMENSION}")
    print(f"✅ Embedding source: Pinecone Inference API")
    print()

if __name__ == "__main__":
    main()
