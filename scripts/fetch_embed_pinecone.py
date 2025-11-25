"""
GPU-Optimized Pipeline for Google Colab T4 GPU
Fetches Quran/Hadith from APIs → Generates embeddings → Uploads to Pinecone
Expected Runtime: 30-40 minutes on T4 GPU
"""

import aiohttp
import asyncio
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
import os
import torch
from tqdm.auto import tqdm
import time
import gc

# ============================================
# GPU CONFIGURATION & VERIFICATION
# ============================================
print("=" * 70)
print("🔍 GPU VERIFICATION")
print("=" * 70)

# Force CUDA device
os.environ['CUDA_VISIBLE_DEVICES'] = '0'
torch.backends.cudnn.benchmark = True  # Optimize for performance

if torch.cuda.is_available():
    print(f"✅ GPU Detected: {torch.cuda.get_device_name(0)}")
    print(f"✅ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    print(f"✅ CUDA Version: {torch.version.cuda}")
    print(f"✅ PyTorch Version: {torch.__version__}")
    device = 'cuda'
else:
    print("❌ WARNING: No GPU detected! This will be VERY SLOW.")
    print("   Please enable T4 GPU: Runtime → Change runtime type → T4 GPU")
    device = 'cpu'

print(f"🎯 Using Device: {device.upper()}")
print("=" * 70)
print()

# ============================================
# CONFIGURATION
# ============================================
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
INDEX_NAME = 'islamic-guidance'
EMBEDDING_MODEL = 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2'
DIMENSION = 768

# API URLs
QURAN_API_BASE = "https://api.alquran.cloud/v1"
HADITH_API_BASES = [
    "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions",
    "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/editions"
]

# Hadith collections (Kutub al-Sittah)
HADITH_COLLECTIONS = [
    "eng-bukhari",
    "eng-muslim", 
    "eng-abudawud",
    "eng-tirmidhi",
    "eng-nasai",
    "eng-ibnmajah"
]

# GPU-optimized batch sizes
GPU_BATCH_SIZE = 128  # Larger batch for T4 GPU (15GB VRAM)
CPU_BATCH_SIZE = 32   # Fallback for CPU
BATCH_SIZE = GPU_BATCH_SIZE if device == 'cuda' else CPU_BATCH_SIZE

print(f"⚙️  Batch Size: {BATCH_SIZE} (optimized for {device.upper()})")
print()

# ============================================
# MODULE 1: API DATA FETCHER
# ============================================
class APIDataFetcher:
    """Fetches Quran and Hadith data from REST APIs"""
    
    def __init__(self):
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=30)
    
    async def __aenter__(self):
        """Initialize async session"""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close async session"""
        if self.session:
            await self.session.close()
    
    async def fetch_quran_all(self):
        """Fetch complete Quran (6236 verses)"""
        print("📖 Fetching complete Quran...")
        url = f"{QURAN_API_BASE}/quran/en.asad"
        
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    print(f"❌ Quran API error: {resp.status}")
                    return []
                
                data = await resp.json()
                
                if not data.get('data', {}).get('surahs'):
                    return []
                
                verses = []
                for surah in data['data']['surahs']:
                    surah_number = surah['number']
                    surah_name = surah['englishName']
                    
                    for ayah in surah['ayahs']:
                        verses.append({
                            'id': f"quran_{surah_number}_{ayah['numberInSurah']}",
                            'source': 'quran',
                            'surah': surah_number,
                            'surah_name': surah_name,
                            'ayah': ayah['numberInSurah'],
                            'text': ayah['text'],
                            'number': ayah['number'],
                            'metadata': {
                                'surah_name': surah_name,
                                'url': f"https://quran.com/{surah_number}:{ayah['numberInSurah']}"
                            }
                        })
                
                print(f"   ✅ Fetched {len(verses)} Quran verses")
                return verses
                
        except Exception as e:
            print(f"   ❌ Error fetching Quran: {e}")
            return []
    
    async def fetch_hadith_collection(self, collection_code: str):
        """Fetch single Hadith collection"""
        book = collection_code.replace('eng-', '')
        print(f"📚 Fetching Hadith: {book}...", end=' ')
        
        for base_url in HADITH_API_BASES:
            url = f"{base_url}/{collection_code}.json"
            
            try:
                async with self.session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        if data.get('hadiths'):
                            hadiths = []
                            for h in data['hadiths']:
                                hadith_number = h.get('hadithnumber', '')
                                
                                hadiths.append({
                                    'id': f"hadith_{book}_{hadith_number}",
                                    'source': 'hadith',
                                    'collection': book,
                                    'number': hadith_number,
                                    'text': h.get('text', ''),
                                    'metadata': {
                                        'book': book,
                                        'narrator': h.get('reference', {}).get('book', ''),
                                        'url': f"https://sunnah.com/{book}:{hadith_number}"
                                    }
                                })
                            
                            print(f"✅ {len(hadiths)} hadiths")
                            return hadiths
                        
            except Exception as e:
                continue
        
        print(f"❌ Failed")
        return []
    
    async def fetch_all_hadiths(self):
        """Fetch all Hadith collections concurrently"""
        print(f"📚 Fetching {len(HADITH_COLLECTIONS)} Hadith collections...")
        
        tasks = [
            self.fetch_hadith_collection(code) 
            for code in HADITH_COLLECTIONS
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Flatten results
        all_hadiths = []
        for collection in results:
            all_hadiths.extend(collection)
        
        print(f"   ✅ Total Hadiths: {len(all_hadiths)}")
        return all_hadiths

# ============================================
# MODULE 2: GPU-OPTIMIZED EMBEDDING GENERATOR
# ============================================
class GPUEmbeddingGenerator:
    """
    GPU-accelerated embedding generation
    Optimized for NVIDIA T4 GPU (15GB VRAM)
    """
    
    def __init__(self, model_name: str = EMBEDDING_MODEL, device: str = device):
        self.device = device
        
        print(f"🧠 Loading embedding model on {device.upper()}...")
        print(f"   Model: {model_name}")
        
        # Load model directly on GPU with optimizations
        self.model = SentenceTransformer(
            model_name,
            device=device
        )
        
        # Enable mixed precision for faster inference on GPU
        if device == 'cuda':
            self.model.half()  # Use FP16 (2x faster, same quality)
            print(f"   ✅ FP16 mode enabled (2x faster)")
        
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        # Verify GPU usage
        if device == 'cuda':
            gpu_memory = torch.cuda.memory_allocated(0) / 1e9
            print(f"   ✅ Model loaded on GPU")
            print(f"   ✅ GPU Memory Used: {gpu_memory:.2f} GB")
        
        print(f"   ✅ Embedding Dimension: {self.dimension}")
        print()
    
    def generate_batch(self, texts: list, batch_size: int = BATCH_SIZE):
        """
        Generate embeddings with GPU acceleration
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size (128 for GPU, 32 for CPU)
        
        Returns:
            numpy array of embeddings
        """
        print(f"🔄 Generating {len(texts)} embeddings...")
        print(f"   Batch Size: {batch_size}")
        print(f"   Device: {self.device.upper()}")
        print()
        
        # Clear GPU cache before starting
        if self.device == 'cuda':
            torch.cuda.empty_cache()
            gc.collect()
        
        # Generate embeddings with progress bar
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
            device=self.device,
            convert_to_tensor=False  # Return numpy for Pinecone
        )
        
        # Clear GPU memory after generation
        if self.device == 'cuda':
            torch.cuda.empty_cache()
        
        print(f"\n   ✅ Generated {len(embeddings)} embeddings")
        print(f"   ✅ Shape: {embeddings.shape}")
        return embeddings

# ============================================
# MODULE 3: PINECONE UPLOADER
# ============================================
class PineconeUploader:
    """Uploads vectors to Pinecone serverless index"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("PINECONE_API_KEY not set")
        
        self.pc = Pinecone(api_key=api_key)
        self.index = None
    
    def initialize_index(self, index_name: str, dimension: int):
        """Create or reset Pinecone index"""
        try:
            # Delete existing index if present
            if index_name in self.pc.list_indexes().names():
                print(f"🗑️  Deleting existing index '{index_name}'...")
                self.pc.delete_index(index_name)
                time.sleep(5)
            
            # Create new serverless index
            print(f"🔨 Creating index '{index_name}'...")
            print(f"   Dimension: {dimension}")
            print(f"   Metric: cosine")
            print(f"   Cloud: AWS (us-east-1)")
            
            self.pc.create_index(
                name=index_name,
                dimension=dimension,
                metric='cosine',
                spec=ServerlessSpec(
                    cloud='aws',
                    region='us-east-1'
                )
            )
            
            # Wait for index to be ready
            print("   ⏳ Waiting for index to be ready...")
            time.sleep(10)
            
            self.index = self.pc.Index(index_name)
            print(f"   ✅ Index '{index_name}' is ready")
            print()
            
        except Exception as e:
            print(f"❌ Error creating index: {e}")
            raise
    
    def upload_batch(self, data: list, embeddings, batch_size: int = 100):
        """
        Upload vectors to Pinecone in batches
        
        Args:
            data: List of data items with metadata
            embeddings: numpy array of embeddings
            batch_size: Vectors per upload batch (max 100)
        """
        if not self.index:
            raise ValueError("Index not initialized")
        
        print(f"☁️  Uploading {len(data)} vectors to Pinecone...")
        print(f"   Batch Size: {batch_size} vectors/request")
        print()
        
        # Prepare vectors
        vectors = []
        for item, embedding in zip(data, embeddings):
            vector = {
                'id': item['id'],
                'values': embedding.tolist() if hasattr(embedding, 'tolist') else embedding,
                'metadata': {
                    'source': item['source'],
                    'text': item['text'][:1000],  # Pinecone metadata limit
                    'url': item['metadata']['url'],
                    # Source-specific metadata
                    **(
                        {
                            'surah': str(item['surah']),
                            'ayah': str(item['ayah']),
                            'surah_name': item['surah_name']
                        } if item['source'] == 'quran' else {
                            'collection': item['collection'],
                            'number': item['number']
                        }
                    )
                }
            }
            vectors.append(vector)
        
        # Upload in batches with progress bar
        total_uploaded = 0
        pbar = tqdm(total=len(vectors), desc="Uploading", unit="vectors")
        
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i+batch_size]
            
            try:
                self.index.upsert(vectors=batch, namespace='')
                total_uploaded += len(batch)
                pbar.update(len(batch))
            except Exception as e:
                print(f"\n❌ Error uploading batch {i}: {e}")
        
        pbar.close()
        print(f"\n   ✅ Uploaded {total_uploaded} vectors")
        return total_uploaded

# ============================================
# MODULE 4: MAIN PIPELINE
# ============================================
async def run_pipeline():
    """
    Main pipeline orchestrator
    Fetch → Embed → Upload
    """
    start_time = time.time()
    
    print("=" * 70)
    print("🚀 STARTING PIPELINE")
    print("=" * 70)
    print()
    
    # ========================================
    # STEP 1: FETCH DATA FROM APIS
    # ========================================
    print("📥 STEP 1/3: Fetching data from APIs")
    print("-" * 70)
    
    async with APIDataFetcher() as fetcher:
        # Fetch Quran and Hadith concurrently
        quran_data, hadith_data = await asyncio.gather(
            fetcher.fetch_quran_all(),
            fetcher.fetch_all_hadiths()
        )
    
    # Combine datasets
    all_data = quran_data + hadith_data
    
    print()
    print("   📊 Fetch Summary:")
    print(f"      - Quran verses: {len(quran_data):,}")
    print(f"      - Hadiths: {len(hadith_data):,}")
    print(f"      - Total records: {len(all_data):,}")
    print()
    
    if not all_data:
        print("❌ No data fetched. Exiting.")
        return
    
    # ========================================
    # STEP 2: GENERATE EMBEDDINGS (GPU)
    # ========================================
    print("🧠 STEP 2/3: Generating embeddings")
    print("-" * 70)
    
    generator = GPUEmbeddingGenerator()
    texts = [item['text'] for item in all_data]
    
    embeddings = generator.generate_batch(texts, batch_size=BATCH_SIZE)
    
    print()
    print(f"   ✅ Embeddings generated: {len(embeddings):,}")
    print(f"   ✅ Dimension: {embeddings.shape[1]}")
    print()
    
    # ========================================
    # STEP 3: UPLOAD TO PINECONE
    # ========================================
    print("☁️  STEP 3/3: Uploading to Pinecone")
    print("-" * 70)
    
    uploader = PineconeUploader(PINECONE_API_KEY)
    uploader.initialize_index(INDEX_NAME, generator.dimension)
    
    total_uploaded = uploader.upload_batch(all_data, embeddings, batch_size=100)
    
    # ========================================
    # VERIFY & SUMMARY
    # ========================================
    print()
    print("🔍 Verifying upload...")
    stats = uploader.index.describe_index_stats()
    
    print()
    print("=" * 70)
    print("🎉 PIPELINE COMPLETE!")
    print("=" * 70)
    print()
    print("📊 Final Statistics:")
    print(f"   - Total vectors in index: {stats['total_vector_count']:,}")
    print(f"   - Dimension: {stats['dimension']}")
    print(f"   - Index name: {INDEX_NAME}")
    print()
    
    elapsed_time = time.time() - start_time
    print(f"⏱️  Total Time: {elapsed_time/60:.1f} minutes")
    print()
    print("✅ Your vector database is ready!")
    print(f"✅ You can now deploy your backend to Vercel")
    print()
    print("=" * 70)

# ============================================
# ENTRY POINT
# ============================================
if __name__ == "__main__":
    # Validate environment
    if not PINECONE_API_KEY:
        print("❌ ERROR: PINECONE_API_KEY not set")
        print("   Set it with: os.environ['PINECONE_API_KEY'] = 'pc-xxxxx'")
        exit(1)
    
    # Run async pipeline
    asyncio.run(run_pipeline())
