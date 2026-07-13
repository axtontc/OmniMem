import requests
import asyncpg
import asyncio

async def test():
    pool = await asyncpg.create_pool('postgresql://omnimem:omnimem_pass@localhost:5432/omnimem_db')
    
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    prompt_emb = model.encode("okay, so does that HELP you remember what Fauxton is? What about the Fractal Architect? Don't look it up manually - the goal should be for omnimem to supply the info").tolist()
    prompt_emb_str = f"[{','.join(map(str, prompt_emb))}]"
    
    await pool.execute("SET hnsw.ef_search = 1000;")
    
    res = await pool.fetch("SELECT count(*) as c FROM semantic_memory WHERE embedding <=> $1::vector < 0.95", prompt_emb_str)
    
    print(f"Total results with ef_search=1000: {res[0]['c']}")
        
    await pool.close()

asyncio.run(test())
