import os
import time
import requests
import json
from pathlib import Path

OMNIMEM_URL = "http://127.0.0.1:8000"
SKILLS_DIR = Path(r"C:\Users\axton\.gemini\config\skills")

def chunk_text(text, chunk_size=800, overlap=100):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += (chunk_size - overlap)
    return chunks

def ingest_skills():
    print(f"--- INGESTING SKILLS TO OMNIMEM ---")
    skill_files = list(SKILLS_DIR.rglob("SKILL.md"))
    print(f"Found {len(skill_files)} skill files.")
    
    total_chunks = 0
    for p in skill_files:
        skill_name = p.parent.name
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            
            chunks = chunk_text(content)
            for idx, chunk in enumerate(chunks):
                payload = {
                    "artifact_id": f"skill_{skill_name}_{idx}",
                    "artifact_type": "skill",
                    "content": chunk,
                    "metadata": {
                        "category": "knowledge",
                        "source": f"Skill: {skill_name}",
                        "chunk_idx": idx
                    }
                }
                
                resp = requests.post(f"{OMNIMEM_URL}/ingest", json=payload, timeout=5)
                if resp.status_code == 200:
                    total_chunks += 1
                else:
                    print(f"Failed to ingest chunk {idx} of {skill_name}: {resp.status_code}")
                    
        except Exception as e:
            print(f"Error processing {skill_name}: {e}")
            
    print(f"Successfully sent {total_chunks} skill chunks to OmniMem for processing.")

if __name__ == "__main__":
    ingest_skills()
