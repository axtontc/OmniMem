import asyncio
from neo4j import GraphDatabase
from omnimem.pgvector_layer import MemoryDB, SemanticMemoryCreate
from mock_deps import Entity, Relation
from omnimem.neo4j_mapping import Neo4jMappingLayer

async def main():
    print("--- LIVE KNOWLEDGE INGESTION TEST ---")
    
    # 1. Connect to PostgreSQL (pgvector)
    dsn = 'postgresql://omnimem:omnimem_pass@localhost:5432/omnimem_db'
    try:
        import asyncpg
        conn = await asyncpg.connect(dsn)
        await conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
        await conn.close()
        
        memory_db = await MemoryDB.create(dsn)
        print("\n[OK] Connected to PostgreSQL + pgvector")
    except Exception as e:
        print(f"\n[FAIL] Could not connect to PostgreSQL: {e}")
        return
    
    # Init DB (Creates tables and extensions if they don't exist)
    await memory_db.init_db()
    print("[OK] Initialized pgvector tables and HNSW indices")
    
    # 2. Connect to Neo4j
    neo4j_uri = "bolt://localhost:7687"
    try:
        neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", "password"))
        # Verify connectivity
        neo4j_driver.verify_connectivity()
        print("[OK] Connected to Neo4j Graph Database")
    except Exception as e:
        print(f"[FAIL] Could not connect to Neo4j: {e}")
        return
    
    # --- INGEST KNOWLEDGE ---
    print("\n--- INGESTING KNOWLEDGE ---")
    
    # Fake embedding for "Agent Swarm Architecture" (384 dimensions)
    vector = [0.01] * 384
    vector[0] = 0.9  
    vector[1] = 0.8
    
    concept = "Fractal Swarm Architecture"
    content = "The Fractal Swarm Architecture utilizes an orchestrator loop and dynamic specialized sub-agents via Swarm Machine Language (SML) on a Redis pub-sub bus."
    
    memory_create = SemanticMemoryCreate(
        concept_name=concept,
        text_content=content,
        embedding=vector,
        metadata={"source": "Axton", "confidence": 1.0}
    )
    
    record_id = await memory_db.store_semantic_memory(memory_create)
    print(f"[+] Stored Semantic Memory in pgvector: UUID {record_id}")
    print(f"    Content: '{content}'")
    
    # Neo4j Entity Ingestion
    agent_entity = Entity(id="concept_swarm", label="Concept", properties={"name": "Fractal Swarm", "domain": "AI"})
    bus_entity = Entity(id="concept_redis", label="Concept", properties={"name": "Redis Event Bus", "type": "Infrastructure"})
    relation = Relation(source_id="concept_swarm", target_id="concept_redis", type="USES_INFRASTRUCTURE", properties={"latency": "<5ms"})
    
    with neo4j_driver.session() as session:
        # Entity 1
        q1, p1 = Neo4jMappingLayer.upsert_entity(agent_entity)
        session.run(q1, **p1)
        # Entity 2
        q2, p2 = Neo4jMappingLayer.upsert_entity(bus_entity)
        session.run(q2, **p2)
        # Relation
        q3, p3 = Neo4jMappingLayer.upsert_relation(relation)
        session.run(q3, **p3)
        
    print(f"[+] Stored Topological Graph in Neo4j:")
    print(f"    (Fractal Swarm) -[USES_INFRASTRUCTURE]-> (Redis Event Bus)")

    # --- RETRIEVE KNOWLEDGE ---
    print("\n--- RETRIEVING KNOWLEDGE ---")
    
    # Query pgvector for similarity
    results = await memory_db.search_semantic_memory(vector, limit=1)
    if results:
        print(f"[RETRIEVED VECTOR] Distance match found!")
        print(f"    Concept: {results[0].concept_name}")
        print(f"    Metadata: {results[0].metadata}")
        print(f"    Stored UUID: {results[0].id}")
    else:
        print("[!] No vector found.")
        
    # Query Neo4j for the subgraph
    with neo4j_driver.session() as session:
        result = session.run(
            "MATCH (a:Concept)-[r:USES_INFRASTRUCTURE]->(b:Concept) RETURN a.name AS src, type(r) AS rel, b.name AS tgt, r.latency AS lat"
        )
        record = result.single()
        if record:
            print(f"[RETRIEVED GRAPH] Subgraph match found!")
            print(f"    Path: ({record['src']}) -[{record['rel']}: {record['lat']}]-> ({record['tgt']})")
        else:
            print("[!] No subgraph found.")
            
    # Cleanup
    await memory_db.close()
    neo4j_driver.close()
    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(main())
