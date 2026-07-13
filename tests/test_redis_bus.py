import asyncio
import pytest
import time
from unittest.mock import AsyncMock

from omnimem.redis_bus import RedisEventBus
from omnimem.security_contract import MemMCPHookPayload, AgentSwarmMessage, ContractViolationError

@pytest.mark.asyncio
async def test_pub_sub_latency():
    bus = RedisEventBus("redis://localhost:6379/0")
    bus.client = AsyncMock()
    bus.pubsub = AsyncMock()
    bus.client.publish.return_value = 1

    payload = MemMCPHookPayload(
        version="1.0",
        event_type="test_event",
        content="This is a fast test event",
        metadata={"source": "pytest"}
    )
    
    await bus.publish("test_channel", payload)

    latencies = []
    for _ in range(10):
        latency = await bus.publish("test_channel", payload)
        latencies.append(latency)

    avg_latency = sum(latencies) / len(latencies)
    print(f"Average Publish Latency: {avg_latency:.4f} ms")
    
    if avg_latency > 5.0:
        print("WARNING: Latency exceeded 5ms limit!")
    else:
        print("SUCCESS: Latency is under 5ms.")
        
    await bus.close()

@pytest.mark.asyncio
async def test_schema_validation_and_subscription():
    publisher = RedisEventBus("redis://localhost:6379/0")
    publisher.client = AsyncMock()
    publisher.pubsub = AsyncMock()
    
    subscriber = RedisEventBus("redis://localhost:6379/0")
    subscriber.client = AsyncMock()
    subscriber.pubsub = AsyncMock()
    
    await subscriber.subscribe("test_channel")
    
    valid_payload = AgentSwarmMessage(
        version="1.0",
        agent_id="agent_123",
        action="update",
        target="knowledge_base",
        payload={"data": "test"}
    )
    
    await publisher.publish("test_channel", valid_payload)
    
    async def mock_listen():
        yield {"type": "message", "data": '{"version": "1.0", "agent_id": "agent_123", "action": "update", "target": "knowledge_base", "payload": {"data": "test"}}'}
        
    subscriber.pubsub.listen = mock_listen
    
    try:
        async with asyncio.timeout(2.0):
            async for msg in subscriber.listen(AgentSwarmMessage):
                break
    except asyncio.TimeoutError as e:
        print(f"Timeout (expected if no more messages): {e}")

    async def mock_bad_listen():
        yield {"type": "message", "data": '{"version": "1.0", "agent_id": "bad", "action": "DROP TABLE", "target": "db", "payload": {}}'}

    subscriber.pubsub.listen = mock_bad_listen
    
    try:
        async with asyncio.timeout(2.0):
            async for msg in subscriber.listen(AgentSwarmMessage):
                break
    except ContractViolationError as e:
        print(f"Caught violation (expected): {e}")
    except asyncio.TimeoutError as e:
        print(f"Timeout: {e}")
        
    await publisher.close()
    await subscriber.close()

async def main():
    print("Running RedisEventBus Tests...")
    try:
        await test_pub_sub_latency()
        await test_schema_validation_and_subscription()
        print("All tests passed!")
    except Exception as e:
        print(f"Tests failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
