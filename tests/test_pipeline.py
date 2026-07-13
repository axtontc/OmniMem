import asyncio
import time
import pytest
from omnimem.pipeline import ContextIngestionPipeline, ContractViolationError

class MockRedisBus:
    async def publish(self, channel: str, message: str) -> None:
        # Simulate network I/O latency < 5ms
        await asyncio.sleep(0.001)

class MockMemoryRouter:
    async def route(self, payload: dict) -> None:
        # Simulate router hand-off latency < 5ms
        await asyncio.sleep(0.002)

@pytest.mark.asyncio
async def test_successful_ingestion_latency():
    import omnimem.api
    omnimem.api.embedding_model = True  # Mock the model loading
    
    redis_bus = MockRedisBus()
    router = MockMemoryRouter()
    pipeline = ContextIngestionPipeline(redis_bus, router)
    
    payload = {
        "artifact_id": "test-artifact-123",
        "artifact_type": "source_code",
        "content": "def foo(): return 'bar'",
        "timestamp": time.time(),
        "metadata": {"source": "ide"}
    }
    
    result = await pipeline.ingest_artifact(payload)
    
    assert result["status"] == "success"
    # Ensure latency is strictly < 20ms
    assert result["latency_ms"] < 20
    assert result["artifact_id"] == "test-artifact-123"

@pytest.mark.asyncio
async def test_fail_fast_validation():
    redis_bus = MockRedisBus()
    router = MockMemoryRouter()
    pipeline = ContextIngestionPipeline(redis_bus, router)
    
    invalid_payload = {
        "artifact_id": "test-artifact-123",
        # Missing required fields like artifact_type, content
    }
    
    with pytest.raises(ContractViolationError) as exc_info:
        await pipeline.ingest_artifact(invalid_payload)
        
    assert "Payload failed validation" in str(exc_info.value)

if __name__ == "__main__":
    asyncio.run(test_successful_ingestion_latency())
    print("Latency and basic correctness tests passed.")
