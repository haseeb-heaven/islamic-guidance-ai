# 1. Database Downloader: download_data.py

import os
import json
import aiohttp
import asyncio
import argparse
from pathlib import Path

QURAN_API = "https://api.alquran.cloud/v1/quran/en.asad"  # Quran with translation
HADITH_BASES = [
    "https://cdn.jsdelivr.net/gh/fawazahmed0/hadith-api@1/editions",
    "https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/editions"
]
HADITH_COLLECTIONS = [
    "eng-bukhari",
    "eng-muslim",
    "eng-abudawud",
    "eng-tirmidhi",
    "eng-nasai",
    "eng-ibnmajah"
]

OUTPUT_DIR = Path("./data")
QURAN_FILE = OUTPUT_DIR / "quran.json"
HADITH_DIR = OUTPUT_DIR / "hadith"

class Downloader:
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()
    
    async def download_quran(self):
        print("Downloading Quran...")
        try:
            async with self.session.get(QURAN_API) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to download Quran: HTTP {resp.status}")
                data = await resp.json()
                return data
        except Exception as e:
            print(f"Error downloading Quran: {e}")
            return None
    
    async def download_hadith_collection(self, collection):
        print(f"Downloading Hadith collection: {collection}")
        for base in HADITH_BASES:
            url = f"{base}/{collection}.json"
            try:
                async with self.session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"Downloaded {len(data.get('hadiths', []))} hadiths from {collection}")
                        return data
            except Exception as e:
                print(f"Error fetching {url}: {e}")
        print(f"Failed to download collection {collection}")
        return None
    
    async def run(self):
        OUTPUT_DIR.mkdir(exist_ok=True)
        HADITH_DIR.mkdir(exist_ok=True)
        
        quran_data = await self.download_quran()
        if quran_data:
            with open(QURAN_FILE, "w", encoding="utf-8") as f:
                json.dump(quran_data, f, ensure_ascii=False, indent=2)
            print(f"Saved Quran to {QURAN_FILE}")
        
        for collection in HADITH_COLLECTIONS:
            data = await self.download_hadith_collection(collection)
            if data:
                with open(HADITH_DIR / f"{collection}.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"Saved Hadith collection {collection} to {HADITH_DIR}")
        

def main():
    parser = argparse.ArgumentParser(description="Download Quran and Hadith JSON data locally")
    args = parser.parse_args()
    
    asyncio.run(run_downloader())

async def run_downloader():
    async with Downloader() as d:
        await d.run()

if __name__ == "__main__":
    main()
