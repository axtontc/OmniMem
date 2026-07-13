import json
import requests
import asyncio
from bs4 import BeautifulSoup
import time
import random
from duckduckgo_search import DDGS

API_URL = "http://127.0.0.1:8000/ingest"

def scrape_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        paragraphs = []
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if len(text) > 100:  # Skip tiny fragments
                paragraphs.append(text)
        return paragraphs
    except Exception as e:
        print(f"[!] Scrape failed for {url}: {e}")
        return []

def search_and_scrape(concept, max_chunks=10):
    """Search DuckDuckGo and scrape top results."""
    all_paragraphs = []
    urls_used = []
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(concept, max_results=2))
            
        for res in results:
            url = res.get('href')
            if not url: continue
            
            urls_used.append(url)
            paras = scrape_url(url)
            
            for p in paras:
                if p not in all_paragraphs:
                    all_paragraphs.append(p)
                if len(all_paragraphs) >= max_chunks:
                    break
            
            if len(all_paragraphs) >= max_chunks:
                break
                
        return urls_used, all_paragraphs[:max_chunks]
        
    except Exception as e:
        print(f"[!] Web search failed for {concept}: {e}")
        return [], []

def ingest_to_omnimem(text_chunk, concept, url, chunk_idx):
    payload = {
        "artifact_id": f"Web_{concept.replace(' ', '')}_Para_{chunk_idx}",
        "artifact_type": "web_scrape",
        "content": text_chunk,
        "metadata": {
            "category": "knowledge",
            "source": "open_web",
            "url": url,
            "chunk_index": chunk_idx
        }
    }
    
    try:
        resp = requests.post(API_URL, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        return False

def run_distillation():
    try:
        with open("extracted_concepts.json", "r") as f:
             concepts = json.load(f)
    except Exception as e:
        print(f"Could not read extracted_concepts.json: {e}")
        return

    print("--- DISTILLING OPEN WEB KNOWLEDGE ---")
    print(f"Concepts to research: {len(concepts)} total targets.")

    total_ingested = 0
    for i, concept in enumerate(concepts):
        print(f"\n[{i+1}/{len(concepts)}] Researching: {concept}")
        urls, chunks = search_and_scrape(concept, max_chunks=8)
        
        if not chunks:
            print("    [!] No chunks found.")
            continue
            
        print(f"    Found sources: {', '.join(urls)}")
        print(f"    Extracted {len(chunks)} semantic chunks. Ingesting to OmniMem...")
        
        ingested_count = 0
        for idx, chunk in enumerate(chunks):
             primary_url = urls[0] if urls else "unknown"
             success = ingest_to_omnimem(chunk, concept, primary_url, idx)
             if success:
                 ingested_count += 1
                 total_ingested += 1
                 
        print(f"    [OK] Ingested {ingested_count} distilled chunks for '{concept}'.")
        time.sleep(random.uniform(1.0, 3.0))
        
    print("\n--- DISTILLATION COMPLETE ---")
    print(f"Total chunks ingested across all topics: {total_ingested}")

if __name__ == "__main__":
    run_distillation()
