import re
from typing import Tuple, Dict, Any, List
from omnimem.models import Entity, Relation, ProceduralKnowledge, ContractViolationError

class Neo4jMappingLayer:
    """
    Neo4j Explicit Topological Mapping Layer.
    Provides Cypher query abstractions for entity mapping, relational schemas,
    and procedural knowledge. Emits queries and parameters for the Memory Router,
    preventing Cypher injection by strictly parameterizing properties and
    sanitizing labels/types.
    """

    @staticmethod
    def _sanitize_identifier(identifier: str) -> str:
        """
        Cypher labels and relationship types cannot be parameterized.
        We must sanitize them against a strict regex to prevent injection.
        """
        if not re.match(r"^[A-Za-z0-9_]+$", identifier):
            raise ContractViolationError(f"Invalid Cypher identifier (label/type): '{identifier}'")
        return identifier

    @classmethod
    def upsert_entity(cls, entity: Entity) -> Tuple[str, Dict[str, Any]]:
        """
        Generates a parameterized Cypher query to MERGE an entity by its ID,
        updating its properties and ensuring the correct label.
        """
        label = cls._sanitize_identifier(entity.label)
        
        query = f"""
        MERGE (n:{label} {{id: $id}})
        SET n += $properties
        RETURN n.id AS id
        """
        params = {
            "id": entity.id,
            "properties": entity.properties
        }
        return query.strip(), params

    @classmethod
    def upsert_relation(cls, relation: Relation) -> Tuple[str, Dict[str, Any]]:
        """
        Generates a parameterized Cypher query to MERGE a relationship
        between a source and target entity. Assumes endpoints already exist
        or handles them generically. For safety, we match nodes by ID regardless of label,
        then merge the relationship.
        """
        rel_type = cls._sanitize_identifier(relation.type)
        
        query = f"""
        MATCH (src {{id: $source_id}})
        MATCH (tgt {{id: $target_id}})
        MERGE (src)-[r:{rel_type}]->(tgt)
        SET r += $properties
        RETURN type(r) AS rel_type
        """
        params = {
            "source_id": relation.source_id,
            "target_id": relation.target_id,
            "properties": relation.properties
        }
        return query.strip(), params

    @classmethod
    def upsert_procedural_knowledge(cls, proc: ProceduralKnowledge) -> Tuple[str, Dict[str, Any]]:
        """
        Maps procedural knowledge into a subgraph.
        Creates a Procedure node and links it to sequential Step nodes.
        Uses UNWIND to efficiently create the step sequence.
        """
        # Using a fixed label for procedural knowledge
        proc_label = "ProceduralKnowledge"
        step_label = "ProcedureStep"
        
        query = f"""
        MERGE (p:{proc_label} {{id: $id}})
        SET p.name = $name, p += $properties
        
        WITH p
        // Clear existing steps to ensure idempotency and correct ordering on updates
        OPTIONAL MATCH (p)-[:HAS_STEP]->(existing_step:{step_label})
        DETACH DELETE existing_step
        
        WITH p
        // If there are no steps, we just stop here but the procedure node is created
        WHERE size($steps) > 0
        
        UNWIND $steps AS step_data
        CREATE (s:{step_label} {{
            id: p.id + '_step_' + toString(step_data.index),
            index: step_data.index,
            content: step_data.content
        }})
        CREATE (p)-[:HAS_STEP {{order: step_data.index}}]->(s)
        
        WITH p, s
        ORDER BY s.index
        WITH p, collect(s) as step_nodes
        
        // Link steps sequentially with NEXT relations (only if >1 step)
        // using WHERE to prevent issues with negative ranges
        CALL {{
            WITH step_nodes
            WITH step_nodes WHERE size(step_nodes) > 1
            UNWIND range(0, size(step_nodes)-2) AS i
            WITH step_nodes[i] AS current, step_nodes[i+1] AS next
            CREATE (current)-[:NEXT_STEP]->(next)
        }}
        
        RETURN count(*) AS operations
        """
        
        # Prepare step data with indices
        steps_with_index = [
            {"index": i, "content": step_content} 
            for i, step_content in enumerate(proc.steps)
        ]
        
        params = {
            "id": proc.id,
            "name": proc.name,
            "properties": proc.properties,
            "steps": steps_with_index
        }
        return query.strip(), params
