import asyncio
import requests
import warnings
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from omnimem.pgvector_layer import MemoryDB, SemanticMemoryCreate

# Suppress HuggingFace warnings for cleaner output
warnings.filterwarnings("ignore")

async def main():
    print("--- FETCHING WIKIPEDIA ---")
    url = "https://en.wikipedia.org/wiki/Machine_learning"
    print(f"Target: {url}")
    
    headers = {'User-Agent': 'OmniMemBot/1.0 (bot@example.com)'}
    resp = requests.get(url, headers=headers)
    print(f"Status: {resp.status_code}, Length: {len(resp.text)}")
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Extract paragraphs
    paragraphs = []
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if len(text) > 80:  # Only meaningful paragraphs
            paragraphs.append(text)
    
    print(f"[OK] Extracted {len(paragraphs)} semantic chunks.")
    
    print("\n--- LOADING EMBEDDING MODEL ---")
    print("Model: sentence-transformers/all-MiniLM-L6-v2")
    # MiniLM produces 384d vectors natively supported by the pgvector schema.
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Connect DB
    dsn = 'postgresql://omnimem:omnimem_pass@localhost:5432/omnimem_db'
    memory_db = await MemoryDB.create(dsn)
    
    print("\n--- INGESTING KNOWLEDGE TO PGVECTOR ---")
    # Ingest the first 30 substantial paragraphs to show the concept
    for i, p in enumerate(paragraphs[:30]): 
        vec_384 = model.encode(p).tolist()
        
        mem = SemanticMemoryCreate(
            concept_name=f"Wiki_ML_Para_{i}",
            text_content=p,
            embedding=vec_384,
            metadata={"source": "wikipedia", "url": url, "chunk_index": i}
        )
        await memory_db.store_semantic_memory(mem)
        
    print(f"[OK] 30 dense semantic vectors committed to Omni-Mem.")
    
    print("\n--- QUERYING OMNI-MEM ---")
    queries = [
        "What is supervised machine learning?",
        "How is machine learning related to statistics?",
        "What is overfitting?"
    ]
    
    for q in queries:
        print(f"\n[?] Query: '{q}'")
        q_vec = model.encode(q).tolist()
        
        # limit=1 to get the absolute closest vector match
        results = await memory_db.search_semantic_memory(q_vec, limit=1)
        if results:
            print(f"    [MATCH FOUND]")
            print(f"    Distance Score: (calculated via HNSW Index)")
            
            # Formatting the text for readability in terminal
            content = results[0].text_content
            if len(content) > 300:
                content = content[:300] + "..."
                
            print(f"    Context: \"{content}\"")
        else:
            print("    [!] No results.")

    await memory_db.close()

if __name__ == "__main__":
    asyncio.run(main())
