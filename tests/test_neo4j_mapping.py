from mock_deps import Entity, Relation, ProceduralKnowledge
from omnimem.neo4j_mapping import Neo4jMappingLayer

def test_entity():
    e = Entity(id="agent_123", label="Agent", properties={"name": "Alice", "role": "Analyzer"})
    query, params = Neo4jMappingLayer.upsert_entity(e)
    assert "MERGE (n:Agent {id: $id})" in query
    assert params["id"] == "agent_123"
    print("Entity test passed.")

def test_relation():
    r = Relation(source_id="agent_123", target_id="task_456", type="ASSIGNED_TO", properties={"weight": 1.0})
    query, params = Neo4jMappingLayer.upsert_relation(r)
    assert "MERGE (src)-[r:ASSIGNED_TO]->(tgt)" in query
    assert params["source_id"] == "agent_123"
    print("Relation test passed.")

def test_procedural_knowledge():
    pk = ProceduralKnowledge(
        id="proc_login",
        name="System Login",
        steps=["Enter username", "Enter password", "Click Submit"],
        properties={"critical": True}
    )
    query, params = Neo4jMappingLayer.upsert_procedural_knowledge(pk)
    assert "MERGE (p:ProceduralKnowledge {id: $id})" in query
    assert "UNWIND $steps AS step_data" in query
    assert "CREATE (current)-[:NEXT_STEP]->(next)" in query
    assert len(params["steps"]) == 3
    print("Procedural Knowledge test passed.")

if __name__ == "__main__":
    test_entity()
    test_relation()
    test_procedural_knowledge()
    print("All tests passed.")
