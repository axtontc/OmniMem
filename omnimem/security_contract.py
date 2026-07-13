import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError, ConfigDict

class ContractViolationError(Exception):
    """Base exception for any API contract or schema violations.
    No swallowed exceptions are permitted across API boundaries;
    all failures must bubble up as structured ContractViolationError responses.
    """
    0

class SecurityException(ContractViolationError):
    """Exception raised for security violations like injection attempts."""
    0

CANARY_TOKEN = "CANARY-8B39-4A7F-9C12-E5D67A9B"

# Basic heuristics for injection detection (SQL/Cypher/Prompt/Tool)
INJECTION_PATTERNS = [
    re.compile(r"--"),  # SQL comment
    re.compile(r";\s*DROP\s+TABLE", re.IGNORECASE),
    re.compile(r";\s*DELETE\s+FROM", re.IGNORECASE),
    re.compile(r"(?<!http:)(?<!https:)//"), # Cypher comment (ignoring URLs)
    re.compile(r"/\*.*?\*/"), # Multi-line comment
    re.compile(r"\bUNION\b\s+\bALL\b", re.IGNORECASE),
    re.compile(r"(?i)ignore\s+(all\s+)?previous\s+(instructions|prompts|commands)"), # Prompt Injection
    re.compile(r"(?i)you\s+are\s+now\s+a\s+"), # Persona Hijack
    re.compile(r"(?i)system\s+(prompt|instruction)"), # System Prompt Leak
    re.compile(r"(?i)</?(tool_call|function_call|call)>"), # Tool Poisoning
]

def sanitize_and_check_security(value: Any) -> Any:
    """
    Recursively checks for security issues like the canary token and injection vectors.
    Sanitizes inputs by rejecting those with known injection patterns or the canary.
    """
    if isinstance(value, str):
        if CANARY_TOKEN in value:
            raise SecurityException(f"Canary token '{CANARY_TOKEN}' detected in input string.")
        
        for pattern in INJECTION_PATTERNS:
            if pattern.search(value):
                # Rejecting input rather than blindly replacing is safer for API contracts
                raise SecurityException(f"Potential injection vector detected: {value}")
        return value
    elif isinstance(value, dict):
        return {k: sanitize_and_check_security(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_and_check_security(v) for v in value]
    return value

class BaseContractModel(BaseModel):
    """Base model enforcing strict Pydantic schemas and security checks."""
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode='before')
    @classmethod
    def run_security_checks(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return sanitize_and_check_security(data)
        return data

class MemMCPHookPayload(BaseContractModel):
    """Schema for Redis Pub/Sub payloads originating from MemMCP."""
    version: str = Field(default="1.0", description="Schema version")
    event_type: str = Field(..., description="Type of the event")
    content: str = Field(..., description="Content or data of the event")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Associated metadata")

    @field_validator('version')
    @classmethod
    def check_version(cls, v: str) -> str:
        # Strict schema diffing and backward compatibility rules
        major_version = v.split(".")[0]
        if major_version != "1":
            raise ContractViolationError(f"Unsupported schema major version: {v}. Expected 1.x.")
        return v

class AgentSwarmMessage(BaseContractModel):
    """Schema for messages originating from the Agent Swarm."""
    version: str = Field(default="1.0")
    agent_id: str
    action: str
    target: str
    payload: Dict[str, Any]

class CeleryTaskSignature(BaseContractModel):
    """Schema for Celery Task Signatures to enforce backward compatibility."""
    version: str = Field(default="1.0")
    task_name: str
    kwargs: Dict[str, Any]
    
    @field_validator('version')
    @classmethod
    def check_version(cls, v: str) -> str:
        major_version = v.split(".")[0]
        if major_version != "1":
            raise ContractViolationError(f"Unsupported schema major version for Celery task: {v}.")
        return v

class GraphEntity(BaseContractModel):
    """Neo4j Ingestion API schema guarantee."""
    node_id: str
    label: str
    properties: Dict[str, Any]

class VectorEmbedding(BaseContractModel):
    """pgvector Ingestion API schema guarantee."""
    id: str
    vector: List[float] = Field(..., description="Dense semantic vector")
    metadata: Dict[str, Any]

class SchemaValidator:
    """Versioned JSON schema validation wrapper for API boundaries."""
    
    @staticmethod
    def validate_payload(model_class: type[BaseModel], data: dict) -> BaseModel:
        try:
            return model_class(**data)
        except ValidationError as e:
            raise ContractViolationError(f"Contract violation for {model_class.__name__}: {e}")
