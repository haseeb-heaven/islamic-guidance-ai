#!/usr/bin/env python3

import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any

from tqdm import tqdm
from dotenv import load_dotenv

from pinecone import Pinecone, PineconeApiException

load_dotenv()

INDEX_NAME = "islamic-guidance"
DATA_DIR = Path("..") / "data"
QURAN_FILE = DATA_DIR / "quran.json"
HADITH_DIR = DATA_DIR / "hadith"

BATCH_SIZE = 50
DELAY_SECONDS = 1.5
MAX_RETRIES = 5

TOPIC_MAP = {
    "emotional_support": [
        "grief", "sad", "sadness", "anxiety", "fear", "despair",
        "hope", "patience", "sabr", "comfort", "heart", "distress",
        "lonely", "depressed", "worry"
    ],
    "finance_wealth": [
        "money", "wealth", "charity", "zakat", "spending", "debt",
        "poor", "rich", "sustenance", "rizq", "loan", "gold", "trade"
    ],
    "marriage_family": [
        "wife", "wives", "husband", "spouse", "marriage", "wedding",
        "divorce", "parents", "mother", "father", "children", "child",
        "family", "kin", "orphan", "relatives"
    ],
    "health_sickness": [
        "sick", "illness", "ill", "cure", "healing", "pain",
        "disease", "health", "medicine", "fever"
    ],
    "forgiveness_sin": [
        "sin", "sins", "repent", "repentance", "forgive", "forgiveness",
        "mercy", "tawbah", "mistake", "wrong", "evil", "hell",
        "punishment", "disobedience"
    ],
    "guidance_faith": [
        "guide", "guidance", "straight path", "path", "truth",
        "lost", "decision", "istikhara", "believe", "belief",
        "faith", "iman", "kufr", "shirk", "islam", "muslim"
    ],
    "lifestyle_manners": [
        "eat", "food", "drink", "sleep", "smile", "laugh", "peace",
        "neighbor", "guest", "manners", "character", "akhlaq", "good deed"
    ],
    "afterlife": [
        "paradise", "jannah", "hell", "jahannam", "hereafter",
        "resurrection", "day of judgment", "grave"
    ]
}

def generate_topics(text: str) -> str:
    t = text.lower()
    topics = set()
    for topic, words in TOPIC_MAP.items():
        if any(w in t for w in words):
            topics.add(topic)
    return " ".join(sorted(topics))

def load_local_items() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    if QURAN_FILE.exists():
        with open(QURAN_FILE, "r", encoding="utf-8") as f:
            quran = json.load(f)["data"]["surahs"]
        for surah in quran:
            for ayah in surah["ayahs"]:
                text = ayah.get("text", "").strip()
                if not text:
                    continue
                items.append({
                    "id": f"quran_{surah['number']}_{ayah['numberInSurah']}",
                    "text": text[:1000],
                    "base_meta": {
                        "source": "quran",
                        "surah": str(surah["number"]),
                        "ayah": str(ayah["numberInSurah"]),
                        "url": f"https://quran.com/{surah['number']}:{ayah['numberInSurah']}"
                    }
                })

    if HADITH_DIR.exists():
        for fp in HADITH_DIR.glob("*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                collection = data.get("metadata", {}).get("name", "unknown").split()[-1].lower()
                for h in data.get("hadiths", []):
                    text = h.get("text", "").strip()
                    if not text:
                        continue
                    num = h.get("hadithnumber", 0)
                    items.append({
                        "id": f"hadith_{collection}_{num}",
                        "text": text[:1000],
                        "base_meta": {
                            "source": "hadith",
                            "collection": collection,
                            "number": str(num),
                            "url": f"https://sunnah.com/{collection}:{num}"
                        }
                    })
            except Exception:
                continue

    return items

def update_metadata_safe(index, items: List[Dict[str, Any]]):
    total = len(items)
    print(f"Updating metadata for {total} records (safe mode)...")

    for i in tqdm(range(0, total, BATCH_SIZE), unit="records", desc="Updating"):
        batch = items[i:i+BATCH_SIZE]

        for item in batch:
            topics = generate_topics(item["text"])
            meta = dict(item["base_meta"])
            meta["text"] = item["text"]  # keep text field in metadata
            meta["topics"] = topics

            retries = 0
            while retries < MAX_RETRIES:
                try:
                    index.update(
                        id=item["id"],
                        set_metadata=meta
                    )
                    break
                except PineconeApiException as e:
                    if e.status == 429:
                        wait = (2 ** retries) * 5
                        time.sleep(wait)
                        retries += 1
                    else:
                        break
                except Exception:
                    break

        time.sleep(DELAY_SECONDS)

def main():
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("PINECONE_API_KEY not set")
        return

    pc = Pinecone(api_key=api_key)
    index = pc.Index(INDEX_NAME)

    items = load_local_items()
    print(f"Loaded {len(items)} local items for tagging.")
    update_metadata_safe(index, items)
    print("Done updating metadata.")

if __name__ == "__main__":
    main()
