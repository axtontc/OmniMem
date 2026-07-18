import asyncio

import asyncpg
import pytest


@pytest.mark.skip(reason="Requires running local PgVector database")
def test_db_search_script():
    async def test():
        from sentence_transformers import SentenceTransformer

        prompt = "okay, so does that HELP you remember what Fauxton is? What about the Fractal Architect? Don't look it up manually - the goal should be for omnimem to supply the info"

        model = SentenceTransformer("all-MiniLM-L6-v2")
        prompt_emb = model.encode(prompt).tolist()
        prompt_emb_str = str(prompt_emb)

        pool = await asyncpg.create_pool("postgresql://postgres:postgres@localhost:5432/omnimem")
        res = await pool.fetch(
            "SELECT count(*) as c FROM semantic_memory WHERE embedding <=> $1::vector < 0.95", prompt_emb_str
        )
        print("Count", res)

        res = await pool.fetch(
            "SELECT concept_name, embedding <=> $1::vector as dist FROM semantic_memory WHERE embedding <=> $1::vector < 0.95 ORDER BY embedding <=> $1::vector LIMIT 10",
            prompt_emb_str,
        )
        for r in res:
            print(r["concept_name"], r["dist"])

    asyncio.run(test())
