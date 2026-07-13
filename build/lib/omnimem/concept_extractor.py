import asyncio
import json
import requests
import random
from typing import List, Dict, Any

from omnimem.pgvector_layer import MemoryDB
from omnimem.neo4j_layer import Neo4jDatabase
from omnimem.neo4j_mapping import Neo4jMappingLayer
from mock_deps import Entity, Relation

# Configuration
OLLAMA_URL = "http://localhost:11434"
DB_DSN = 'postgresql://omnimem:omnimem_pass@localhost:5432/omnimem_db'
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "password"

def get_best_ollama_model():
    """Dynamically find the best local model."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            if models:
                model_names = [m["name"] for m in models]
                for pref in ["llama3", "phi3", "mistral"]:
                    for mn in model_names:
                        if pref in mn:
                            return mn
                return model_names[0]
    except Exception as e:
        print(f"[!] Warning: Could not connect to Ollama tags endpoint: {e}")
    return "llama3"

def ask_ollama(model_name: str, prompt: str) -> List[Dict[str, Any]]:
    try:
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }, timeout=120)
        
        if resp.status_code == 200:
            response_text = resp.json().get("response", "[]").strip()
            
            # Clean up potential markdown blocks from Ollama
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            elif response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            response_text = response_text.strip()
            
            try:
                data = json.loads(response_text)
                return data
            except json.JSONDecodeError:
                print(f"[FAIL] Could not parse LLM output as JSON:\nRaw Output:\n{response_text}\n")
    except Exception as e:
        print(f"[FAIL] LLM extraction failed: {e}")
    return []

async def extract_concepts():
    print("--- FETCHING SAMPLES FROM OMNIMEM API ---")
    
    try:
        neo4j_db = Neo4jDatabase(NEO4J_URI, NEO4J_USER, NEO4J_PASS)
        await neo4j_db.connect()
    except Exception as e:
         print(f"[FAIL] Could not connect to Neo4j DB: {e}")
         return

    try:
        resp = requests.post("http://127.0.0.1:8000/search", json={
            "query_text": "Fauxton autonomous reviewer agent",
            "limit": 30,
            "max_distance": 1.0
        }, timeout=10)
        
        if resp.status_code != 200:
            print(f"[!] API Search Failed: {resp.status_code} {resp.text}")
            await neo4j_db.close()
            return
            
        results = resp.json()
    except Exception as e:
        print(f"[FAIL] API connection failed: {e}")
        await neo4j_db.close()
        return
        
    if not results:
        print("[!] No data returned from OmniMem to analyze.")
        await neo4j_db.close()
        return

    samples = [res.get("text_content", "") for res in results if res.get("text_content")]
    random.shuffle(samples)
    context_text = "\n\n---\n\n".join(samples[:5])
    
    if len(context_text) > 4000:
        context_text = context_text[:4000]
        
    print(f"[DEBUG] Context text length: {len(context_text)}")
        
    model_name = get_best_ollama_model()
    print(f"[OK] Using Ollama model: {model_name}")
    print("--- PHASE 1: EXTRACTING GRAPH TRIPLES ---")
    
    prompt = f"""
    You are an expert systems architect.
    Read the following text snippets and extract key relationships between technical concepts discussed.
    You MUST extract Entity-Relationship-Entity triples.
    
    Return ONLY a valid JSON array of objects. Each object must have:
    - "source": string (Name of the first concept, strictly alphanumeric/underscores, e.g. "SML")
    - "target": string (Name of the second concept, strictly alphanumeric/underscores, e.g. "Fractal_Swarm")
    - "relation": string (The relationship verb in uppercase, e.g. "USES", "IMPLEMENTS", "RELATES_TO")
    - "source_desc": string (Brief description of the source concept)
    - "target_desc": string (Brief description of the target concept)
    
    TEXT:
    {context_text}
    """
    
    triples = ask_ollama(model_name, prompt)
    print(f"[DEBUG] Raw triples parsed: {triples}")
    
    # Sometimes the model wraps the array in a dict like {"data": [...]} or {"triples": [...]}
    if isinstance(triples, dict):
        for key in triples.keys():
            if isinstance(triples[key], list):
                triples = triples[key]
                break
        if isinstance(triples, dict):
             triples = [triples] # Fallback if it's just a single object
        
    if not triples or not isinstance(triples, list):
        print("[!] OLLAMA FAILED or returned invalid format.")
        await neo4j_db.close()
        return
        
    print(f"[OK] Extracted {len(triples)} triples. Pushing to Neo4j...")
    
    queries = []
    for item in triples:
        source_id = item.get("source", "").strip().replace(" ", "_")
        target_id = item.get("target", "").strip().replace(" ", "_")
        rel_type = item.get("relation", "RELATES_TO").strip().upper().replace(" ", "_")
        
        if not source_id or not target_id:
            continue
            
        # Ensure labels/types are alphanumeric for cypher safety
        import re
        source_id = re.sub(r'[^A-Za-z0-9_]', '', source_id)
        target_id = re.sub(r'[^A-Za-z0-9_]', '', target_id)
        rel_type = re.sub(r'[^A-Za-z0-9_]', '', rel_type)
        
        if not source_id or not target_id or not rel_type:
            continue
            
        # 1. Upsert Source Entity
        src_entity = Entity(id=source_id, label="Concept", properties={"description": item.get("source_desc", "")})
        q, p = Neo4jMappingLayer.upsert_entity(src_entity)
        queries.append((q, p))
        
        # 2. Upsert Target Entity
        tgt_entity = Entity(id=target_id, label="Concept", properties={"description": item.get("target_desc", "")})
        q, p = Neo4jMappingLayer.upsert_entity(tgt_entity)
        queries.append((q, p))
        
        # 3. Upsert Relation
        relation = Relation(source_id=source_id, target_id=target_id, type=rel_type, properties={})
        q, p = Neo4jMappingLayer.upsert_relation(relation)
        queries.append((q, p))
        
        print(f"  -> ({source_id}) -[{rel_type}]-> ({target_id})")

    if queries:
        try:
            await neo4j_db.execute_transaction(queries)
            print(f"\n[OK] Successfully pushed {len(queries)//3} relationships to Neo4j Graph!")
        except Exception as e:
            print(f"[FAIL] Neo4j Transaction Failed: {e}")
            
    await neo4j_db.close()

if __name__ == "__main__":
    asyncio.run(extract_concepts())
