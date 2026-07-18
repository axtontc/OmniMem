import os

from omnimem.celery_app import app
from omnimem.exceptions import ContractViolationError
from omnimem.ipc_wal import AsyncWAL
from omnimem.models import Entity, Relation
from omnimem.neo4j_mapping import Neo4jMappingLayer
from omnimem.schemas import EmbeddingRequest, GraphAggregationRequest, validate_payload

wal = AsyncWAL(wal_dir=os.path.join(os.path.dirname(__file__), "wal_logs"))


def _generate_embedding_logic(payload: dict):
    # Mocking CPU/GPU heavy lifting
    # Interaction with T5 pgvector is expected here
    return {"status": "success", "embedding": [0.1, 0.2, 0.3], "model": payload.get("model_version")}


def _aggregate_graph_logic(payload: dict):
    # Mocking graph traversal aggregation
    # Interaction with T6 Neo4j is expected here
    return {"status": "success", "aggregated_nodes": [payload.get("node_id"), "node_y", "node_z"]}


@app.task(bind=True, max_retries=3)
def generate_embedding_task(self, payload: dict, **kwargs):
    # Backward compatible task signatures: uses kwargs for future args
    try:
        # Validate using Pydantic (T2)
        validated = validate_payload(EmbeddingRequest, payload)

        # Execute with WAL/IPC (T3)
        return wal.execute_with_lock(
            task_name="generate_embedding",
            payload=validated.model_dump(),
            operation=lambda: _generate_embedding_logic(validated.model_dump()),
        )
    except ContractViolationError as e:
        # Zero swallowed exceptions: must explicitly raise or return error
        raise e
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries)


@app.task(bind=True, max_retries=3)
def aggregate_graph_task(self, payload: dict, **kwargs):
    try:
        validated = validate_payload(GraphAggregationRequest, payload)

        return wal.execute_with_lock(
            task_name="aggregate_graph",
            payload=validated.model_dump(),
            operation=lambda: _aggregate_graph_logic(validated.model_dump()),
        )
    except ContractViolationError as e:
        raise e
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries)


def _ingest_vector_logic(payload: dict):
    import asyncio

    from pgvector_layer import MemoryDB, SemanticMemoryCreate

    async def do_write():
        db = await MemoryDB.create("postgresql://omnimem:omnimem_pass@localhost:5432/omnimem_db")
        try:
            await db.store_semantic_memory(
                SemanticMemoryCreate(
                    concept_name=payload.get("id", "unknown"),
                    text_content=payload["text"],
                    embedding=payload["vector"],
                    metadata=payload.get("metadata", {}),
                )
            )
        finally:
            await db.close()

    asyncio.run(do_write())
    return {"status": "success", "id": payload.get("id")}


@app.task(bind=True, max_retries=3, name="tasks.ingest_vector")
def ingest_vector(self, **kwargs):
    try:
        return wal.execute_with_lock(
            task_name="ingest_vector", payload=kwargs, operation=lambda: _ingest_vector_logic(kwargs)
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries)


def _ingest_graph_logic(payload: dict):
    import asyncio

    from neo4j_layer import Neo4jDatabase

    async def do_write():
        # Connect to Neo4j
        neo4j_db = Neo4jDatabase(uri="bolt://localhost:7687", user="neo4j", password="password")
        await neo4j_db.connect()
        try:
            queries = []
            # Map Entities
            for e_dict in payload.get("entities", []):
                ent = Entity(**e_dict)
                q, p = Neo4jMappingLayer.upsert_entity(ent)
                queries.append((q, p))

            # Map Relationships
            for r_dict in payload.get("relationships", []):
                rel = Relation(**r_dict)
                q, p = Neo4jMappingLayer.upsert_relation(rel)
                queries.append((q, p))

            if queries:
                await neo4j_db.execute_transaction(queries)
        finally:
            await neo4j_db.close()

    asyncio.run(do_write())
    return {
        "status": "success",
        "entities_count": len(payload.get("entities", [])),
        "relationships_count": len(payload.get("relationships", [])),
    }


@app.task(bind=True, max_retries=3, name="tasks.ingest_graph")
def ingest_graph(self, **kwargs):
    try:
        return wal.execute_with_lock(
            task_name="ingest_graph", payload=kwargs, operation=lambda: _ingest_graph_logic(kwargs)
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries)
