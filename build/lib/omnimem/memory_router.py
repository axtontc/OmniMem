"""
T9: Memory Router (Z_2 Zone)
Coordinates operations between pgvector (T5), Neo4j (T6), and Celery (T8).
Guarantees Graph/Vector data conforms strictly to RPC schemas.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationError

class ContractViolationError(Exception):
    """Raised when data does not conform to established RPC schemas."""
    0

class VectorEmbedding(BaseModel):
    id: str
    text: str = Field(..., description="The original text segment")
    vector: List[float] = Field(..., min_length=1, description="The dense semantic embedding")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class GraphEntity(BaseModel):
    id: str
    label: str = Field(..., pattern=r"^[A-Za-z0-9_]+$")
    properties: Dict[str, Any] = Field(default_factory=dict)

class GraphRelationship(BaseModel):
    source_id: str
    target_id: str
    type: str = Field(..., pattern=r"^[A-Z_]+$")
    properties: Dict[str, Any] = Field(default_factory=dict)

class MemoryPayload(BaseModel):
    entities: List[GraphEntity] = Field(default_factory=list)
    relationships: List[GraphRelationship] = Field(default_factory=list)
    embeddings: List[VectorEmbedding] = Field(default_factory=list)

class MemoryRouter:
    def __init__(self, celery_app: Any):
        """
        Initializes the Memory Router Z_2 Zone.
        Takes a Celery app instance to dispatch tasks to Z_1 workers (T8).
        The workers will handle the direct writes to pgvector (T5) and Neo4j (T6).
        """
        self.celery = celery_app

    def validate_payload(self, raw_data: Dict[str, Any]) -> MemoryPayload:
        """
        Validates the incoming payload against RPC schemas.
        All inputs MUST be sanitized and validated *before* hitting Celery.
        """
        try:
            return MemoryPayload(**raw_data)
        except ValidationError as e:
            raise ContractViolationError(f"Payload validation failed: {e.json()}")
        except Exception as e:
            # No swallowed exceptions
            raise ContractViolationError(f"Unexpected serialization error: {str(e)}")

    def sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Basic sanitization to prevent injection in properties.
        Recursively converts values to safe types, drops invalid keys.
        """
        sanitized = {}
        for k, v in data.items():
            if not isinstance(k, str):
                continue
            # Very basic string sanitization placeholder
            if isinstance(v, str):
                sanitized[k] = v.replace("'", "''")  # Escape single quotes
            elif isinstance(v, (int, float, bool, type(None))):
                sanitized[k] = v
            elif isinstance(v, list):
                sanitized[k] = [self.sanitize_dict(item) if isinstance(item, dict) else item for item in v]
            elif isinstance(v, dict):
                sanitized[k] = self.sanitize_dict(v)
        return sanitized

    def route_memory(self, raw_data: Dict[str, Any]) -> str:
        """
        Validates, sanitizes, and routes memory elements to respective Celery tasks.
        """
        payload = self.validate_payload(raw_data)
        
        # Dispatch Vector Embeddings to Celery for pgvector ingestion (T5) via Z_1
        if payload.embeddings:
            for emb in payload.embeddings:
                sanitized_metadata = self.sanitize_dict(emb.metadata or {})
                self.celery.send_task(
                    'tasks.ingest_vector', 
                    kwargs={
                        "id": emb.id,
                        "text": emb.text,
                        "vector": emb.vector,
                        "metadata": sanitized_metadata
                    }
                )

        # Dispatch Graph Topological Data to Celery for Neo4j ingestion (T6) via Z_1
        if payload.entities or payload.relationships:
            sanitized_entities = [
                {
                    "id": e.id,
                    "label": e.label,
                    "properties": self.sanitize_dict(e.properties)
                } for e in payload.entities
            ]
            sanitized_relationships = [
                {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "type": r.type,
                    "properties": self.sanitize_dict(r.properties)
                } for r in payload.relationships
            ]
            
            self.celery.send_task(
                'tasks.ingest_graph', 
                kwargs={
                    "entities": sanitized_entities,
                    "relationships": sanitized_relationships
                }
            )
            
        return "Memory routed successfully via Z_2 Zone"
