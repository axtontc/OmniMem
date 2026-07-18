from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from omnimem.exceptions import ContractViolationError


class EmbeddingRequest(BaseModel):
    # Backward compatible schemas: use defaults for new fields
    text: str
    model_version: str = Field(default="v1.0")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class GraphAggregationRequest(BaseModel):
    node_id: str
    depth: int = Field(default=1)
    relationship_types: Optional[List[str]] = Field(default_factory=list)
    idempotency_key: Optional[str] = None


def validate_payload(schema_class, payload: dict):
    try:
        return schema_class(**payload)
    except ValidationError as e:
        raise ContractViolationError(f"Payload validation failed for {schema_class.__name__}: {e}")
