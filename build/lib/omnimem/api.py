import time
from typing import Dict, Any, List
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from omnimem.redis_bus import RedisEventBus
from omnimem.memory_router import MemoryRouter
from omnimem.pipeline import ContextIngestionPipeline
from omnimem.pgvector_layer import MemoryDB
from omnimem.neo4j_layer import Neo4jDatabase
from omnimem.celery_app import app as celery_app

class IngestRequest(BaseModel):
    artifact_id: str
    artifact_type: str
    content: str
    metadata: Dict[str, Any] = {}

class SearchRequest(BaseModel):
    query_text: str
    limit: int = 5
    max_distance: float = 0.6

class GraphSearchRequest(BaseModel):
    keywords: List[str]
    limit: int = 10

# Global instances
redis_bus = RedisEventBus()
memory_router = MemoryRouter(celery_app=celery_app)
pipeline = ContextIngestionPipeline(redis_bus=redis_bus, memory_router=memory_router)
memory_db = None
graph_db = None
embedding_model = None
DB_DSN = 'postgresql://omnimem:omnimem_pass@localhost:5432/omnimem_db'

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global memory_db, graph_db, embedding_model
    await redis_bus.connect()
    memory_db = await MemoryDB.create(DB_DSN)
    
    graph_db = Neo4jDatabase(uri="bolt://localhost:7687", user="neo4j", password="password")
    await graph_db.connect()
    
    from sentence_transformers import SentenceTransformer
    import warnings
    warnings.filterwarnings("ignore")
    print("Loading embedding model...")
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print("[OK] Omni-Mem API Gateway Online")
    yield
    # Shutdown
    await redis_bus.close()
    if memory_db:
        await memory_db.close()
    if graph_db:
        await graph_db.close()
    print("[OK] Omni-Mem API Gateway Offline")

app = FastAPI(title="Omni-Mem API Gateway", lifespan=lifespan)

@app.post("/ingest")
async def ingest_memory(req: IngestRequest):
    """Pushes memory payload to the Redis bus for async processing by Celery."""
    payload = {
        "artifact_id": req.artifact_id,
        "artifact_type": req.artifact_type,
        "content": req.content,
        "timestamp": time.time(),
        "metadata": req.metadata
    }
    
    try:
        result = await pipeline.ingest_artifact(payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/search")
async def search_memory(req: SearchRequest):
    """Synchronously queries the pgvector layer for semantic matches."""
    try:
        vec_384 = embedding_model.encode(req.query_text).tolist()
        results = await memory_db.search_semantic_memory(vec_384, limit=req.limit, max_distance=req.max_distance)
        return [
            {
                "id": r.id,
                "concept_name": r.concept_name,
                "text_content": r.text_content,
                "metadata": r.metadata,
                "created_at": r.created_at.isoformat() if hasattr(r.created_at, 'isoformat') else r.created_at
            }
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search_graph")
async def search_graph(req: GraphSearchRequest):
    """Queries the Neo4j graph layer for topological matches."""
    try:
        results = await graph_db.search_graph(keywords=req.keywords, limit=req.limit)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

