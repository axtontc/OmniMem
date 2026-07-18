import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

import asyncpg
from pgvector.asyncpg import register_vector
from pydantic import Field, field_validator

# Adjust sys.path to allow imports from T1 and T2 sandboxes
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from omnimem.security_contract import BaseContractModel, ContractViolationError


class DatabaseIntegrityError(ContractViolationError):
    """Raised when an asyncpg constraint or data error occurs, mapping it to a contract violation."""

    0


class SemanticMemoryCreate(BaseContractModel):
    """Schema for creating a new semantic memory."""

    concept_name: str = Field(..., description="Name of the concept/entity")
    text_content: str = Field(..., description="Text content to be embedded")
    embedding: List[float] = Field(..., description="Vector embedding of the text (dimension 384)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary JSON metadata")

    @field_validator("embedding")
    @classmethod
    def validate_dimension(cls, v: List[float]) -> List[float]:
        if len(v) != 384:
            raise ContractViolationError(f"Embedding dimension must be exactly 384, got {len(v)}")
        return v


class SemanticMemoryRecord(SemanticMemoryCreate):
    """Schema for a retrieved semantic memory record."""

    id: str = Field(..., description="UUID of the memory")
    created_at: datetime
    updated_at: datetime


class EpisodicLogCreate(BaseContractModel):
    """Schema for logging a new episode."""

    agent_id: str = Field(..., description="ID of the agent generating the log")
    event_type: str = Field(..., description="Type/category of the event")
    event_content: str = Field(..., description="Textual description of the event")
    embedding: List[float] = Field(..., description="Vector embedding of the event (dimension 384)")

    @field_validator("embedding")
    @classmethod
    def validate_dimension(cls, v: List[float]) -> List[float]:
        if len(v) != 384:
            raise ContractViolationError(f"Embedding dimension must be exactly 384, got {len(v)}")
        return v


class EpisodicLogRecord(EpisodicLogCreate):
    """Schema for a retrieved episodic log record."""

    id: str = Field(..., description="UUID of the episodic log")
    created_at: datetime


class MemoryDB:
    """
    CRUD Abstraction layer for pgvector dense semantic memory and episodic logs.
    Handles connection pooling and vector type registration.
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize with an asyncpg pool.
        The pool should be created with `MemoryDB.create(dsn)` to ensure pgvector types are registered.
        """
        self.pool = pool

    @classmethod
    async def create(cls, dsn: str) -> "MemoryDB":
        """
        Create a new MemoryDB instance by initializing a connection pool.
        Uses an init callback to run `await register_vector(conn)` on every new connection.
        """

        async def init(conn):
            await register_vector(conn)

        try:
            pool = await asyncpg.create_pool(dsn, init=init)
            if not pool:
                raise DatabaseIntegrityError("Failed to initialize asyncpg pool.")
            return cls(pool)
        except asyncpg.PostgresError as e:
            raise DatabaseIntegrityError(f"Database connection error: {str(e)}")

    async def init_db(self) -> None:
        """
        Run DDL to set up the database schemas.
        Creates the `vector` extension if not exists.
        Creates `semantic_memory` and `episodic_logs` tables.
        Creates HNSW indices on the embedding columns.
        """
        try:
            await self.pool.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            await self.pool.execute("""
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    concept_name VARCHAR(255) NOT NULL,
                    text_content TEXT NOT NULL,
                    embedding VECTOR(384) NOT NULL,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            # Flaw 7 Fix: Idempotently add UNIQUE constraint after cleaning duplicates
            await self.pool.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'semantic_memory_concept_name_key'
                    ) THEN
                        DELETE FROM semantic_memory a USING semantic_memory b
                        WHERE a.id < b.id AND a.concept_name = b.concept_name;

                        ALTER TABLE semantic_memory ADD CONSTRAINT semantic_memory_concept_name_key UNIQUE (concept_name);
                    END IF;
                END;
                $$;
            """)

            await self.pool.execute("""
                CREATE INDEX IF NOT EXISTS semantic_memory_embedding_idx
                ON semantic_memory USING hnsw (embedding vector_cosine_ops);
            """)

            await self.pool.execute("""
                CREATE TABLE IF NOT EXISTS episodic_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    agent_id VARCHAR(255) NOT NULL,
                    event_type VARCHAR(255) NOT NULL,
                    event_content TEXT NOT NULL,
                    embedding VECTOR(384) NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            """)

            await self.pool.execute("""
                CREATE INDEX IF NOT EXISTS episodic_logs_embedding_idx
                ON episodic_logs USING hnsw (embedding vector_cosine_ops);
            """)
        except asyncpg.PostgresError as e:
            raise DatabaseIntegrityError(f"Database initialization error: {str(e)}")

    async def store_semantic_memory(self, data: SemanticMemoryCreate) -> str:
        """
        Store a new semantic memory in the database.
        Returns the generated UUID as a string.
        Catches asyncpg exceptions and re-raises them as DatabaseIntegrityError.
        """
        query = """
            INSERT INTO semantic_memory (concept_name, text_content, embedding, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            ON CONFLICT (concept_name) DO UPDATE SET
                text_content = EXCLUDED.text_content,
                embedding = EXCLUDED.embedding,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING id;
        """
        try:
            metadata_json = json.dumps(data.metadata)
            record_id = await self.pool.fetchval(
                query, data.concept_name, data.text_content, data.embedding, metadata_json
            )
            return str(record_id)
        except asyncpg.PostgresError as e:
            raise DatabaseIntegrityError(f"Error storing semantic memory: {str(e)}")

    async def search_semantic_memory(
        self, query_embedding: List[float], limit: int = 5, max_distance: float = 0.6
    ) -> List[SemanticMemoryRecord]:
        """
        Search for semantically similar memories using L2 distance or cosine similarity via HNSW index.
        Returns a list of SemanticMemoryRecord.
        Catches asyncpg exceptions and re-raises them as DatabaseIntegrityError.
        """
        if len(query_embedding) != 384:
            raise ContractViolationError("Query embedding dimension must be exactly 384.")

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("SET LOCAL hnsw.ef_search = 1000;")
                    rows = await conn.fetch(
                        """
                        SELECT id, concept_name, text_content, embedding, metadata, created_at, updated_at
                        FROM semantic_memory
                        WHERE embedding <=> $1 < $3
                        ORDER BY embedding <=> $1
                        LIMIT $2;
                    """,
                        query_embedding,
                        limit,
                        max_distance,
                    )

            results = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                results.append(
                    SemanticMemoryRecord(
                        id=str(row["id"]),
                        concept_name=row["concept_name"],
                        text_content=row["text_content"],
                        embedding=row["embedding"].to_list()
                        if hasattr(row["embedding"], "to_list")
                        else [float(x) for x in str(row["embedding"]).strip("[]").split(",")],
                        metadata=metadata,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )
            return results
        except asyncpg.PostgresError as e:
            raise DatabaseIntegrityError(f"Error searching semantic memory: {str(e)}")

    async def log_episode(self, data: EpisodicLogCreate) -> str:
        """
        Log a new episodic event in the database.
        Returns the generated UUID as a string.
        Catches asyncpg exceptions and re-raises them as DatabaseIntegrityError.
        """
        query = """
            INSERT INTO episodic_logs (agent_id, event_type, event_content, embedding)
            VALUES ($1, $2, $3, $4)
            RETURNING id;
        """
        try:
            record_id = await self.pool.fetchval(
                query, data.agent_id, data.event_type, data.event_content, data.embedding
            )
            return str(record_id)
        except asyncpg.PostgresError as e:
            raise DatabaseIntegrityError(f"Error logging episode: {str(e)}")

    async def search_episodes(self, query_embedding: List[float], limit: int = 5) -> List[EpisodicLogRecord]:
        """
        Search for semantically similar episodic logs using HNSW index.
        Returns a list of EpisodicLogRecord.
        Catches asyncpg exceptions and re-raises them as DatabaseIntegrityError.
        """
        if len(query_embedding) != 384:
            raise ContractViolationError("Query embedding dimension must be exactly 384.")

        query = """
            SELECT id, agent_id, event_type, event_content, embedding, created_at
            FROM episodic_logs
            ORDER BY embedding <-> $1
            LIMIT $2;
        """
        try:
            rows = await self.pool.fetch(query, query_embedding, limit)
            results = []
            for row in rows:
                results.append(
                    EpisodicLogRecord(
                        id=str(row["id"]),
                        agent_id=row["agent_id"],
                        event_type=row["event_type"],
                        event_content=row["event_content"],
                        embedding=row["embedding"],
                        created_at=row["created_at"],
                    )
                )
            return results
        except asyncpg.PostgresError as e:
            raise DatabaseIntegrityError(f"Error searching episodes: {str(e)}")

    async def close(self):
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
