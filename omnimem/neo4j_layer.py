import os
from neo4j import AsyncGraphDatabase
from typing import List, Dict, Any, Tuple

class Neo4jDatabase:
    def __init__(self, uri, user, password):
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None

    async def connect(self):
        self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.user, self.password))
        
    async def close(self):
        if self.driver:
            await self.driver.close()

    async def execute_query(self, query: str, parameters: dict = None):
        if not self.driver:
            raise RuntimeError("Neo4j driver not connected.")
        async with self.driver.session() as session:
            result = await session.run(query, parameters)
            return await result.data()
            
    async def execute_transaction(self, queries: List[Tuple[str, dict]]):
        if not self.driver:
            raise RuntimeError("Neo4j driver not connected.")
        async with self.driver.session() as session:
            async def _tx_func(tx):
                results = []
                for q, p in queries:
                    res = await tx.run(q, p)
                    results.append(await res.data())
                return results
            return await session.execute_write(_tx_func)

    async def search_graph(self, keywords: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Simple keyword-based graph search. 
        Matches nodes whose ID contain the keywords,
        and returns them along with their immediate relationships.
        """
        if not keywords:
            return []
            
        where_clauses = []
        for i in range(len(keywords)):
            where_clauses.append(f"toLower(n.id) CONTAINS toLower($kw_{i})")
        
        where_stmt = " OR ".join(where_clauses)
        params = {f"kw_{i}": kw for i, kw in enumerate(keywords)}
        params["limit"] = limit
        
        # Pull the node, plus up to 5 immediate neighbors to avoid massive bloat
        query = f"""
        MATCH (n)
        WHERE {where_stmt}
        WITH n LIMIT $limit
        OPTIONAL MATCH (n)-[r]-(m)
        WITH n, r, m LIMIT 5
        RETURN 
            n.id AS id, 
            labels(n) AS labels, 
            n AS properties,
            collect({{type: type(r), neighbor: m.id}}) AS relationships
        """
        return await self.execute_query(query, params)
