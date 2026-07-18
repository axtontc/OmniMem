import asyncio

import asyncpg
import pytest
from sentence_transformers import SentenceTransformer


@pytest.mark.skip(reason="Requires running local PgVector database")
def test_dist_script():
    async def test():
        prompt = "okay, so does that HELP you remember what Fauxton is? What about the Fractal Architect? Don't look it up manually - the goal should be for omnimem to supply the info"

        model = SentenceTransformer("all-MiniLM-L6-v2")
        prompt_emb = model.encode(prompt).tolist()
        prompt_emb_str = str(prompt_emb)

        pool = await asyncpg.create_pool("postgresql://postgres:postgres@localhost:5432/omnimem")
        res = await pool.fetch(
            "SELECT concept_name, embedding <=> $1::vector as dist FROM semantic_memory WHERE concept_name ILIKE '%fauxton%'",
            prompt_emb_str,
        )

        print("Distances for Fauxton skills:")
        for r in res:
            print(f"{r['concept_name']}: {r['dist']}")

        await pool.close()

    asyncio.run(test())
