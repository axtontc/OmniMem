import os
import requests
from pathlib import Path

# Target directory
TARGET_DIR = Path(r"C:\Users\axton\.gemini\config\skills\knowledge-librarian\handbooks")
API_URL = "http://127.0.0.1:8000/ingest"

# Exclude directories and file types
EXCLUDE_DIRS = {".venv", ".pytest_cache", ".git", "__pycache__"}
ALLOWED_EXTENSIONS = {".md", ".txt"}
MAX_FILES = 200  # Safety limit
CHUNK_SIZE = 1000

def chunk_text(text, chunk_size):
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def main():
    print(f"--- STARTING HANDBOOK INGESTION ---")
    print(f"Target: {TARGET_DIR}")
    
    files_processed = 0
    chunks_sent = 0
    
    for root, dirs, files in os.walk(TARGET_DIR):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        
        for file in files:
            file_path = Path(root) / file
            
            if file_path.suffix not in ALLOWED_EXTENSIONS:
                continue
                
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"[!] Skipping {file_path.name}: {e}")
                continue
                
            if not content.strip():
                continue
                
            # Chunk the file
            chunks = chunk_text(content, CHUNK_SIZE)
            
            for i, chunk in enumerate(chunks):
                payload = {
                    "artifact_id": f"{file_path.name}_part_{i}",
                    "artifact_type": "handbook",
                    "content": chunk,
                    "metadata": {
                        "source": "knowledge_librarian",
                        "filepath": str(file_path),
                        "chunk_index": i
                    }
                }
                
                try:
                    resp = requests.post(API_URL, json=payload, timeout=5)
                    if resp.status_code == 200:
                        chunks_sent += 1
                    else:
                        print(f"[!] Error pushing {payload['artifact_id']}: {resp.status_code} {resp.text}")
                except Exception as e:
                    print(f"[FAIL] Could not connect to API: {e}")
                    return
            
            files_processed += 1
            if files_processed >= MAX_FILES:
                print(f"\n[!] Reached MAX_FILES limit ({MAX_FILES}). Stopping early to protect resources.")
                break
                
        if files_processed >= MAX_FILES:
            break
            
    print(f"\n[OK] Handbook Ingestion Complete.")
    print(f"     Processed Files: {files_processed}")
    print(f"     Chunks Vectorized: {chunks_sent}")

if __name__ == "__main__":
    main()
