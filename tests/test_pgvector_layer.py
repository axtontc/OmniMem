import pytest
import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from omnimem.pgvector_layer import (
    MemoryDB, 
    SemanticMemoryCreate, 
    EpisodicLogCreate, 
    DatabaseIntegrityError,
    ContractViolationError
)

@pytest.fixture
def mock_pool():
    pool = AsyncMock()
    pool.execute = AsyncMock()
    pool.fetchval = AsyncMock()
    pool.fetch = AsyncMock()
    return pool

@pytest.mark.asyncio
async def test_init_db(mock_pool):
    db = MemoryDB(mock_pool)
    await db.init_db()
    assert mock_pool.execute.call_count >= 3
    # Check that pgvector extension and tables are created
    calls = mock_pool.execute.call_args_list
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in call[0][0] for call in calls)
    assert any("CREATE TABLE IF NOT EXISTS semantic_memory" in call[0][0] for call in calls)
    assert any("CREATE TABLE IF NOT EXISTS episodic_logs" in call[0][0] for call in calls)

@pytest.mark.asyncio
async def test_store_semantic_memory(mock_pool):
    db = MemoryDB(mock_pool)
    mock_pool.fetchval.return_value = "123e4567-e89b-12d3-a456-426614174000"
    
    data = SemanticMemoryCreate(
        concept_name="test_concept",
        text_content="This is a test concept",
        embedding=[0.1] * 384,
        metadata={"source": "test"}
    )
    
    memory_id = await db.store_semantic_memory(data)
    assert memory_id == "123e4567-e89b-12d3-a456-426614174000"
    mock_pool.fetchval.assert_called_once()
    args = mock_pool.fetchval.call_args[0]
    assert "INSERT INTO semantic_memory" in args[0]
    # Check that data is passed to the query
    assert data.concept_name in args
    assert data.text_content in args

@pytest.mark.asyncio
async def test_search_semantic_memory(mock_pool):
    db = MemoryDB(mock_pool)
    
    mock_conn = AsyncMock()
    mock_conn.fetch.return_value = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "concept_name": "test_concept",
            "text_content": "This is a test concept",
            "embedding": [0.1] * 384,
            "metadata": '{"source": "test"}',
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }
    ]
    
    mock_acquire = AsyncMock()
    mock_acquire.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value = mock_acquire
    
    results = await db.search_semantic_memory([0.1] * 384, limit=5)
    assert len(results) == 1
    assert results[0].concept_name == "test_concept"
    mock_conn.fetch.assert_called_once()
    assert "ORDER BY embedding <->" in mock_conn.fetch.call_args[0][0]

@pytest.mark.asyncio
async def test_database_integrity_error_propagation(mock_pool):
    import asyncpg
    db = MemoryDB(mock_pool)
    mock_pool.fetchval.side_effect = asyncpg.exceptions.UniqueViolationError("duplicate key")
    
    data = EpisodicLogCreate(
        agent_id="agent_1",
        event_type="thought",
        event_content="Thinking...",
        embedding=[0.2] * 384
    )
    
    with pytest.raises(DatabaseIntegrityError):
        await db.log_episode(data)

@pytest.mark.asyncio
async def test_contract_violation_on_invalid_data():
    with pytest.raises(ContractViolationError):
        SemanticMemoryCreate(
            concept_name="test_concept",
            text_content="This is a test concept",
            embedding=[0.1] * 10, # Validates purely by typing at the moment, assuming List[float] is checked by Pydantic.
            metadata={"source": "test"}
        )
