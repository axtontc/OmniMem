from enum import Enum
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError


class SMLIntent(str, Enum):
    DELEGATE = "DELEGATE"
    INFORM = "INFORM"
    QUERY = "QUERY"
    RESULT = "RESULT"
    BLOCK = "BLOCK"
    ACK = "ACK"
    EXECUTE_TASK = "EXECUTE_TASK"


class SMLContext(BaseModel):
    files: Optional[List[str]] = None
    facts: Optional[List[str]] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    blocked_by: Optional[List[str]] = None
    # Support arbitrary additional context fields that might be sent by Swarm-Lead
    model_config = {"extra": "allow"}


class SMLConstraints(BaseModel):
    must: Optional[List[str]] = None
    must_not: Optional[List[str]] = None


class SMLMessage(BaseModel):
    a2a_msg: str = "1.0"
    src: str
    dst: str
    intent: SMLIntent
    context: Optional[SMLContext] = None
    payload: str
    constraints: Optional[SMLConstraints] = None
    expect: Optional[str] = None


class SMLParseError(Exception):
    """Raised when SML YAML is malformed or violates schema constraints."""

    0


class SMLAdapter:
    @staticmethod
    def parse(yaml_content: str) -> SMLMessage:
        """Parse a raw YAML string into an SMLMessage object."""
        try:
            # Strip markdown code blocks if present
            yaml_content = yaml_content.strip()
            if yaml_content.startswith("```yaml"):
                yaml_content = yaml_content[7:]
            elif yaml_content.startswith("```"):
                yaml_content = yaml_content[3:]
            if yaml_content.endswith("```"):
                yaml_content = yaml_content[:-3]

            data = yaml.safe_load(yaml_content)
            if not isinstance(data, dict):
                raise SMLParseError("YAML content must resolve to a dictionary.")
            return SMLMessage(**data)
        except yaml.YAMLError as e:
            raise SMLParseError(f"YAML parsing error: {e}")
        except ValidationError as e:
            raise SMLParseError(f"SML Schema validation error: {e}")

    @staticmethod
    def serialize(message: SMLMessage) -> str:
        """Serialize an SMLMessage object to a raw YAML string."""
        data = message.model_dump(exclude_none=True)
        # Convert intent Enum to string
        if isinstance(data.get("intent"), Enum):
            data["intent"] = data["intent"].value

        yaml_str = yaml.dump(data, sort_keys=False, default_flow_style=False)
        return f"```yaml\n{yaml_str}```"
