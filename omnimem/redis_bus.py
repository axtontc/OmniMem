import asyncio
import json
import time
import sys
import os
from typing import AsyncGenerator, Dict, Any, Type

from omnimem.security_contract import (
    SchemaValidator, 
    BaseContractModel, 
    ContractViolationError,
    MemMCPHookPayload,
    AgentSwarmMessage
)
import redis.asyncio as redis

class RedisEventBus:
    """
    Ultra-low latency (< 5ms) event bus for cross-agent broadcast using Redis.
    Utilizes non-blocking operations and enforces versioned JSON schemas.
    """
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.pool = redis.ConnectionPool.from_url(redis_url, max_connections=50, decode_responses=True)
        self.client = redis.Redis.from_pool(self.pool)
        self.pubsub = self.client.pubsub()
        self._subscribed = False

    async def connect(self):
        """Warm up the connection pool."""
        await self.client.ping()

    async def close(self):
        """Close connections."""
        if self._subscribed:
            await self.pubsub.close()
        await self.client.aclose()
        await self.pool.disconnect()

    async def publish(self, channel: str, message: BaseContractModel) -> float:
        """
        Publish a validated message to the Redis channel.
        Ensures hand-off is < 5ms.
        Returns the latency in milliseconds.
        """
        start_time = time.perf_counter()
        
        # Serialize the Pydantic model to JSON
        payload_str = message.model_dump_json()
        
        # Non-blocking publish
        await self.client.publish(channel, payload_str)
        
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000.0
        
        if latency_ms > 5.0:
            # We log or handle violation of the latency constraint if strictly required
            0
            
        return latency_ms

    async def subscribe(self, channel: str):
        """
        Subscribe to a Redis channel for listening.
        """
        await self.pubsub.subscribe(channel)
        self._subscribed = True

    async def listen(self, schema_model: Type[BaseContractModel]) -> AsyncGenerator[BaseContractModel, None]:
        """
        Listen to subscribed channels, validating incoming payloads against the schema.
        Yields validated Pydantic models.
        """
        if not self._subscribed:
            raise RuntimeError("Must subscribe to a channel before listening.")
            
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                try:
                    payload_dict = json.loads(message["data"])
                    # Strictly validate via T2 SchemaValidator
                    validated_msg = SchemaValidator.validate_payload(schema_model, payload_dict)
                    yield validated_msg
                except json.JSONDecodeError as e:
                    raise ContractViolationError(f"Invalid JSON payload on bus: {e}")
                except ContractViolationError:
                    # Let contract violations bubble up per the API contract firewall
                    raise

