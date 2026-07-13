from typing import Dict, Any, List

class Entity:
    def __init__(self, id: str, label: str, properties: Dict[str, Any]):
        self.id = id
        self.label = label
        self.properties = properties

class Relation:
    def __init__(self, source_id: str, target_id: str, type: str, properties: Dict[str, Any]):
        self.source_id = source_id
        self.target_id = target_id
        self.type = type
        self.properties = properties

class ProceduralKnowledge:
    def __init__(self, id: str, name: str, steps: List[str], properties: Dict[str, Any]):
        self.id = id
        self.name = name
        self.steps = steps
        self.properties = properties

class ContractViolationError(Exception):
    pass
