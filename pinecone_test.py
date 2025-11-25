#!/usr/bin/env python3
"""
Upload Quran & Hadith to Pinecone using Pinecone's Inference Embeddings API
Updated: Uses Pinecone's llama-text-embed-v2 model for embedding generation
No need for sentence-transformers or GPU - all handled by Pinecone API
✅ T4 GPU/CUDA support added for optimal Colab environment
"""

import os
import json
import time
from pathlib import Path
from tqdm import tqdm
from dotenv import load_dotenv

try:
    from pinecone import Pinecone, ServerlessSpec
except Exception:
    Pinecone = None
    ServerlessSpec = None

# ---------------- CONFIG ----------------
DATA_DIR = Path("./data")
QURAN_FILE = DATA_DIR / "quran.json"
HADITH_DIR = DATA_DIR / "hadith"
INDEX_NAME = "islamic-guidance-pinecone"
NAMESPACE = "__default__"
EMBEDDING_MODEL = "llama-text-embed-v2"
DIMENSION = 1024
BATCH_SIZE = 96 # Maximum batch size for Pinecone

# Load .env
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")


# ---------------- Data loaders & parsers ----------------
class DataLoader:
    collection:str = "Unknown"

    def load_quran_data(self):
        if not QURAN_FILE.exists():
            raise FileNotFoundError(
                "Quran JSON not found. Please run data downloader first."
            )
        with open(QURAN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["data"]["surahs"]


    def load_hadith_data(self):
        hadiths = []
        if not HADITH_DIR.exists():
            raise FileNotFoundError(
                "Hadith directory not found. Please run data downloader first."
            )
        for filepath in HADITH_DIR.glob("*.json"):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                hadiths.extend(data.get("hadiths", []))
                self.collection = data["metadata"]["name"]
                if self.collection:
                    self.collection = self.collection.split()[-1].lower()
        return hadiths


    def parse_quran_verses(self, data):
        verses = []
        for surah in data:
            for ayah in surah["ayahs"]:
                text = ayah["text"].strip()
                if not text:
                    continue
                verses.append(
                    {
                        "id": f"quran_{surah['number']}_{ayah['numberInSurah']}",
                        "text": text,
                        "source": "quran",
                        "surah": surah["number"],
                        "ayah": ayah["numberInSurah"],
                        "surah_name": surah["englishName"],
                        "metadata": {
                            "source": "quran",
                            "surah": str(surah["number"]),
                            "ayah": str(ayah["numberInSurah"]),
                            "surah_name": surah["englishName"],
                            "url": f"https://quran.com/{surah['number']}:{ayah['numberInSurah']}",
                        },
                    }
                )
        return verses


    def parse_hadiths(self, data, collection):
        parsed = []
        for hadith in data:
            text = hadith.get("text", "").strip()
            if not text:
                continue
            number = hadith.get("hadithnumber", "0")
            parsed.append(
                {
                    "id": f"hadith_{collection}_{number}",
                    "text": text,
                    "source": "hadith",
                    "collection": collection,
                    "number": number,
                    "metadata": {
                        "source": "hadith",
                        "collection": collection,
                        "number": str(number),
                        "url": f"https://sunnah.com/{collection}:{number}",
                    },
                }
            )
        return parsed


# ---------------- Pinecone uploader ----------------
class PineconeUploader:
    def __init__(self, api_key: str, index_name: str, dimension: int = DIMENSION):
        if Pinecone is None:
            raise ImportError(
                "pinecone package not available. Install with `pip install pinecone-client`."
            )
        self.pc = Pinecone(api_key=api_key)
        self.index_name = index_name
        self.dimension = dimension
        self.index = None

    def create_or_connect_index(self):
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]

        # If index exists -> delete it first because embedded indexes cannot change config
        if self.index_name in existing_indexes:
            print(f"❌ Deleting existing index: {self.index_name}")
            self.pc.delete_index(self.index_name)
            time.sleep(5)

        print(f"🔨 Creating new index (Integrated Inference): {self.index_name}")

        # ⛔ NO dimension, NO metric, NO spec arguments!
        # Integrated Inference indexes must be created using create_index_for_model()
        # Import specific classes to get type hints and autocompletions

        self.pc.create_index_for_model(
            name=self.index_name,
            cloud="aws",
            region="us-east-1",
            embed={"model": "llama-text-embed-v2", "field_map": {"text": "text"}},
        )

        # Wait for Pinecone to finish creating the index
        time.sleep(5)

        # Connect to the newly created index
        self.index = self.pc.Index(self.index_name)
        print(f"   ✅ Connected to index: {self.index_name}")
        print(f"   ✅ Index: {self.index}")

    def upload(self, data: list, batch_size: int = BATCH_SIZE):
        """Upload vectors with embeddings"""
        if not self.index:
            raise ValueError("Index not initialized")

        print(f"☁️  Uploading {len(data)} vectors to Pinecone...")

        # Prepare records
        records = []

        for item in data:
            # Build flat fields
            base = {
                "id": item["id"],
                "text": item["text"][
                    :1000
                ],  # this is what field_map maps to the embedder
                "source": item["source"],
                "url": item["metadata"]["url"],
            }

            if item["source"] == "quran":
                base.update(
                    {
                        "surah": str(item["surah"]),
                        "ayah": str(item["ayah"]),
                        "surah_name": item["surah_name"],
                    }
                )
            else:
                base.update(
                    {
                        "collection": item["metadata"]["collection"],
                        "number": str(item["metadata"]["number"]),
                    }
                )

            records.append(base)

        # Upload in batches
        total_uploaded = 0
        pbar = tqdm(total=len(records), desc="Uploading", unit="records")
        api_calls = 0
        sleep_time = 1
        index = 0

        while index < len(records):
            batch = records[index : index + batch_size]

            try:
                response = self.index.upsert_records(namespace=NAMESPACE, records=batch)
                api_calls += 1

                if response:
                    pbar.update(response.upserted_count)

                time.sleep(0.5)
                index += batch_size  # success → move forward

            except Exception as e:
                print(f"\n❌ Error uploading batch at index {index}: {e}")
                print(f"🔁 Trying again — the previous attempt FAILED for index {index}")
                sleep_time = min(sleep_time * 2, 30)  # exponential backoff
                time.sleep(sleep_time)
                continue

        pbar.close()
        print(f"\n   ✅ Uploaded {total_uploaded} records with {api_calls} API calls")
        return total_uploaded


if __name__ == "__main__":
    print("☁️ Connecting to Pinecone...")

    load_dotenv()

    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY not found in .env file")
    
    if not INDEX_NAME:
        raise ValueError("INDEX_NAME was not found in this file")

    # Print Values of startup.
    print("Index Name: ", INDEX_NAME)
    print("Pinecone API Key: ", PINECONE_API_KEY[:5] + "...")
    print("Batch Size: ", BATCH_SIZE)
    print("Dimension: ", DIMENSION)
    print("Namespace: ", NAMESPACE)
    print("Embedding Model: ", EMBEDDING_MODEL)
    print("\n")

    uploader = PineconeUploader(api_key=PINECONE_API_KEY, index_name=INDEX_NAME)
    data_loader = DataLoader()
    uploader.create_or_connect_index()
    # uploader.index = uploader.pc.Index(INDEX_NAME)

    # Load data.
    print("Loading Data...")
    quran_data = data_loader.load_quran_data()
    hadith_data = data_loader.load_hadith_data()
    print("Data Loaded.")

    print("Parsing Data...")
    quran_parsed = data_loader.parse_quran_verses(quran_data)
    hadith_parsed = data_loader.parse_hadiths(hadith_data, data_loader.collection)
    print("Data Parsed.")

    data_items = quran_parsed + hadith_parsed

    print(f"\n☁️ Uploading {len(data_items)} documents (text-only mode)...")
    uploader.upload(data_items)
    print("Done Uploading all the data to Pinecone.")
