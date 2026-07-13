import asyncpg
import asyncio
from sentence_transformers import SentenceTransformer
import json

async def test():
    model = SentenceTransformer('all-MiniLM-L6-v2')
    prompt_emb = model.encode("okay, so does that HELP you remember what Fauxton is? What about the Fractal Architect? Don't look it up manually - the goal should be for omnimem to supply the info").tolist()
    prompt_emb_str = f"[{','.join(map(str, prompt_emb))}]"
    
    pool = await asyncpg.create_pool('postgresql://omnimem:omnimem_pass@localhost:5432/omnimem_db')
    
    res = await pool.fetch("SELECT concept_name, embedding <=> $1::vector as dist FROM semantic_memory WHERE concept_name ILIKE '%fauxton%'", prompt_emb_str)
    
    print("Distances for Fauxton skills:")
    for r in res:
        print(f"{r['concept_name']}: {r['dist']}")
        
    await pool.close()

asyncio.run(test())
