from unittest.mock import MagicMock

import pytest

from omnimem.memory_router import (
    ContractViolationError,
    MemoryRouter,
)


def test_valid_payload():
    mock_celery = MagicMock()
    router = MemoryRouter(mock_celery)

    valid_data = {
        "embeddings": [{"id": "v1", "text": "hello", "vector": [0.1, 0.2, 0.3], "metadata": {"source": "test"}}],
        "entities": [{"id": "e1", "label": "Person", "properties": {"name": "Alice"}}],
        "relationships": [{"source_id": "e1", "target_id": "e2", "type": "KNOWS", "properties": {"since": 2021}}],
    }

    result = router.route_memory(valid_data)
    assert result == "Memory routed successfully via Z_2 Zone"

    # Check that celery tasks were sent
    assert mock_celery.send_task.call_count == 2

    call_args_list = mock_celery.send_task.call_args_list
    assert call_args_list[0][0][0] == "tasks.ingest_vector"
    assert call_args_list[1][0][0] == "tasks.ingest_graph"


def test_invalid_vector():
    mock_celery = MagicMock()
    router = MemoryRouter(mock_celery)

    invalid_data = {
        "embeddings": [
            {"id": "v1", "text": "hello", "vector": []}  # vector is empty, validation should fail
        ]
    }

    with pytest.raises(ContractViolationError) as excinfo:
        router.route_memory(invalid_data)

    assert "Payload validation failed" in str(excinfo.value)


def test_invalid_entity_label():
    mock_celery = MagicMock()
    router = MemoryRouter(mock_celery)

    invalid_data = {
        "entities": [
            {
                "id": "e1",
                "label": "Invalid Label!",
                "properties": {},
            }  # Label contains space and !, not allowed by pattern
        ]
    }

    with pytest.raises(ContractViolationError):
        router.route_memory(invalid_data)


def test_sanitization():
    mock_celery = MagicMock()
    router = MemoryRouter(mock_celery)

    data = {"entities": [{"id": "e1", "label": "Person", "properties": {"name": "O'Connor", "age": 30}}]}

    router.route_memory(data)

    # Check args
    call_args = mock_celery.send_task.call_args_list[0]
    kwargs = call_args[1]["kwargs"]

    assert kwargs["entities"][0]["properties"]["name"] == "O''Connor"
    assert kwargs["entities"][0]["properties"]["age"] == 30
