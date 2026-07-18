import asyncio
import time
from typing import Any, Dict

from pydantic import BaseModel, ValidationError


class ContractViolationError(Exception):
    """Exception raised when an API contract is violated (T2 requirement)."""

    0


class ArtifactPayload(BaseModel):
    artifact_id: str
    artifact_type: str
    content: str
    timestamp: float
    metadata: Dict[str, Any] = {}


class ContextIngestionPipeline:
    def __init__(self, redis_bus, memory_router):
        """
        Initialize the ingestion pipeline with references to the Redis Bus (T4)
        and Memory Router (T9).
        """
        self.redis_bus = redis_bus
        self.memory_router = memory_router

    async def ingest_artifact(self, raw_payload: dict) -> Dict[str, Any]:
        """
        Ingest live IDE/environment context.
        Guarantee < 20ms hand-off latencies. Apply strict fail-fast parsing.
        """
        start_time = time.perf_counter()

        # 1. Strict fail-fast parsing (T10 Requirement)
        try:
            artifact = ArtifactPayload.model_validate(raw_payload)
        except ValidationError as e:
            raise ContractViolationError(f"Payload failed validation: {e}")

        # 2. Asynchronous dispatch to Redis Bus (T4) and Memory Router (T9)
        try:
            await asyncio.gather(self._stream_to_redis(artifact), self._stream_to_router(artifact))
        except Exception as e:
            # No swallowed exceptions - bubble up as structured error
            raise ContractViolationError(f"Stream dispatch failed: {e}")

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return {"status": "success", "latency_ms": elapsed_ms, "artifact_id": artifact.artifact_id}

    async def _stream_to_redis(self, artifact: ArtifactPayload) -> None:
        """Stream to T4 Redis Bus."""
        # Await the publish method of the mock/real redis bus
        await self.redis_bus.publish("context_stream", artifact)

    async def _stream_to_router(self, artifact: ArtifactPayload) -> None:
        """Stream to T9 Memory Router."""
        import asyncio

        # We can dynamically import the embedding_model from api to avoid circular imports,
        # or just instantiate a new one. Since api.py has it loaded, let's fetch it.
        from omnimem.api import embedding_model

        if not embedding_model:
            raise ContractViolationError("Embedding model not loaded")

        vec_384 = embedding_model.encode(artifact.content).tolist()

        memory_payload = {
            "embeddings": [
                {"id": artifact.artifact_id, "text": artifact.content, "vector": vec_384, "metadata": artifact.metadata}
            ]
        }
        await asyncio.to_thread(self.memory_router.route_memory, memory_payload)
