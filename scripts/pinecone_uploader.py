#!/usr/bin/env python3
"""
Pinecone Uploader - SAFE MODE
Optimized to AVOID Rate Limits (RPM) and handle Quotas gracefully.
Strategy: Sequential uploads, 2-second delay between batches.
"""

import os
import json
import time
import logging
import itertools
from pathlib import Path
from typing import List, Dict, Any, Generator

from tqdm import tqdm
from dotenv import load_dotenv

# USE STANDARD CLIENT
try:
    from pinecone import Pinecone, PineconeApiException
except ImportError:
    raise ImportError("Run: pip install pinecone-client")

# ============================================================================
# CONFIGURATION (STRICT LIMITS)
# ============================================================================

BATCH_SIZE = 90        # Safe batch size (under 96 max)
DELAY_SECONDS = 2.0    # Wait 2s between requests = ~30 RPM (Safe limit)
MAX_RETRIES = 5        # Retry failed batches up to 5 times

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

logger = setup_logger(__name__)

# ============================================================================
# DATA LOADING (Unchanged)
# ============================================================================

def load_data(data_dir: Path) -> List[Dict[str, Any]]:
    records = []
    
    # Load Quran
    quran_path = data_dir / "quran.json"
    if quran_path.exists():
        with open(quran_path, "r", encoding="utf-8") as f:
            quran = json.load(f)["data"]["surahs"]
            for surah in quran:
                for ayah in surah["ayahs"]:
                    text = ayah.get("text", "").strip()
                    if text:
                        records.append({
                            "id": f"quran_{surah['number']}_{ayah['numberInSurah']}",
                            "text": text[:1000],
                            "source": "quran",
                            "surah": str(surah['number']),
                            "ayah": str(ayah['numberInSurah']),
                            "url": f"https://quran.com/{surah['number']}:{ayah['numberInSurah']}"
                        })
    
    # Load Hadith
    hadith_dir = data_dir / "hadith"
    if hadith_dir.exists():
        for file_path in hadith_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    collection = data.get("metadata", {}).get("name", "unknown").split()[-1].lower()
                    for h in data.get("hadiths", []):
                        text = h.get("text", "").strip()
                        if text:
                            records.append({
                                "id": f"hadith_{collection}_{h.get('hadithnumber', 0)}",
                                "text": text[:1000],
                                "source": "hadith",
                                "collection": collection,
                                "number": str(h.get("hadithnumber", 0)),
                                "url": f"https://sunnah.com/{collection}:{h.get('hadithnumber', 0)}"
                            })
            except Exception:
                pass

    return records

# ============================================================================
# UPLOADER (SAFE MODE)
# ============================================================================

def upload_safe(index, records):
    total = len(records)
    logger.info(f"Starting SAFE upload for {total} records...")
    logger.info(f"Batch Size: {BATCH_SIZE} | Delay: {DELAY_SECONDS}s | Est. Time: {(total/BATCH_SIZE*DELAY_SECONDS)/60:.1f} mins")

    # Create batches
    batches = [records[i:i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    
    uploaded_count = 0
    
    # Progress bar
    pbar = tqdm(total=total, unit="records")
    
    for batch_idx, batch in enumerate(batches):
        retry_count = 0
        success = False
        
        while not success and retry_count < MAX_RETRIES:
            try:
                # UPLOAD
                index.upsert_records(
                    namespace="__default__",
                    records=batch
                )
                
                # SUCCESS
                success = True
                uploaded_count += len(batch)
                pbar.update(len(batch))
                
                # CRITICAL: Wait to respect RPM
                time.sleep(DELAY_SECONDS)

            except PineconeApiException as e:
                # Handle Rate Limits (429) & Errors
                if e.status == 429:
                    wait_time = (2 ** retry_count) * 5  # Exponential backoff: 5s, 10s, 20s...
                    logger.warning(f"[RATE LIMIT] Batch {batch_idx} throttled. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    logger.error(f"[ERROR] Batch {batch_idx} failed: {e}")
                    break # Fatal error, skip batch
            except Exception as e:
                logger.error(f"[ERROR] Unexpected: {e}")
                break
        
        if not success:
            logger.error(f"[FAIL] Could not upload Batch {batch_idx} after retries.")

    pbar.close()
    return uploaded_count

# ============================================================================
# MAIN
# ============================================================================

def main():
    load_dotenv()
    api_key = os.getenv("PINECONE_API_KEY")
    
    if not api_key:
        print("ERROR: PINECONE_API_KEY not found in .env")
        return

    try:
        # Connect
        pc = Pinecone(api_key=api_key)
        index_name = "islamic-guidance"
        
        # Setup Index (Create if missing)
        existing = [i.name for i in pc.list_indexes()]
        if index_name not in existing:
            logger.info(f"Creating index: {index_name}")
            pc.create_index_for_model(
                name=index_name,
                cloud="aws",
                region="us-east-1",
                embed={"model": "llama-text-embed-v2", "field_map": {"text": "text"}}
            )
            time.sleep(10) # Wait for ready
        
        index = pc.Index(index_name)
        
        # Load & Upload
        data = load_data(Path("./data"))
        logger.info(f"Loaded {len(data)} records.")
        
        upload_safe(index, data)
        
        logger.info("Upload Complete.")

    except Exception as e:
        logger.error(f"Fatal Error: {e}")

if __name__ == "__main__":
    main()
