from typing import Any, Dict, List

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """
    Represents a core knowledge node in the Graph database.
    """

    id: str = Field(..., description="Unique identifier for the entity.")
    label: str = Field(..., description="The ontological category or type of the entity.")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Metadata and properties.")


class Relation(BaseModel):
    """
    Represents a directional relationship between two entities.
    """

    source_id: str = Field(..., description="ID of the source entity.")
    target_id: str = Field(..., description="ID of the target entity.")
    type: str = Field(..., description="The type of the relationship (e.g., ASSIGNED_TO, DEPENDS_ON).")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Metadata and properties for the edge.")


class ProceduralKnowledge(BaseModel):
    """
    Represents a sequential process or workflow mapped into the graph.
    """

    id: str = Field(..., description="Unique identifier for the procedure.")
    name: str = Field(..., description="Human-readable name of the procedure.")
    steps: List[str] = Field(..., description="Sequential steps comprising the procedure.")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata.")


class ContractViolationError(Exception):
    """
    Raised when a core system invariant or security contract is violated.
    """

    pass
