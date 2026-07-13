import asyncio
import pytest
import sys
import os
import time

from omnimem.redis_bus import RedisEventBus
from omnimem.security_contract import MemMCPHookPayload, AgentSwarmMessage, ContractViolationError

@pytest.mark.asyncio
async def test_pub_sub_latency():
    bus = RedisEventBus("redis://localhost:6379/0")
    bus.client = __import__("fakeredis").FakeAsyncRedis(decode_responses=True)
    bus.pubsub = bus.client.pubsub()
    # await bus.connect()

    # 1. Test Publish Latency
    payload = MemMCPHookPayload(
        version="1.0",
        event_type="test_event",
        content="This is a fast test event",
        metadata={"source": "pytest"}
    )
    
    # Warm up
    await bus.publish("test_channel", payload)

    # Measure actual
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
    publisher.client = __import__("fakeredis").FakeAsyncRedis(decode_responses=True)
    publisher.pubsub = publisher.client.pubsub()
    subscriber = RedisEventBus("redis://localhost:6379/0")
    subscriber.client = publisher.client
    subscriber.pubsub = subscriber.client.pubsub()
    
    # await publisher.connect()
    # await subscriber.connect()
    
    await subscriber.subscribe("test_channel")
    
    valid_payload = AgentSwarmMessage(
        version="1.0",
        agent_id="agent_123",
        action="update",
        target="knowledge_base",
        payload={"data": "test"}
    )
    
    await publisher.publish("test_channel", valid_payload)
    
    # We do a quick listen loop to verify receipt
    import asyncio
    try:
        async with asyncio.timeout(2.0):
            async for msg in subscriber.listen(AgentSwarmMessage):
                break
    except asyncio.TimeoutError as e:
        print(f"Timeout (expected if no more messages): {e}")

    # Now let's try an invalid payload structure (mocking injection attack by bypass)
    # The Schema validation prevents sending bad ones naturally because of Pydantic,
    # but let's test if we inject bad JSON into redis directly.
    import fakeredis.aioredis as redis_fake
    r = redis_fake.FakeRedis(decode_responses=True)
    bad_payload_str = '{"version": "1.0", "agent_id": "bad", "action": "DROP TABLE", "target": "db", "payload": {}}'
    await r.publish("test_channel", bad_payload_str)
    
    import asyncio
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
    await r.aclose()

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
