# T5: pgvector Dense Semantic Memory Layer - Implementation Plan

## 1. Objectives
- Implement PostgreSQL (pgvector) table schemas for dense semantic memory, episodic logs, and text embeddings.
- Develop CRUD abstractions (Python) to interact with these schemas.
- Ensure strict adherence to Pydantic-based API contracts (simulating dependency on T2).

## 2. Dependency Mapping
- **T1 (Infrastructure)**: PostgreSQL with `pgvector` extension enabled. `sandbox_T1.core.config` provides the connection URI.
- **T2 (Security/Contracts)**: `sandbox_T2.security_contract` provides `BaseContractModel`, `ContractViolationError`, and `VectorEmbedding`. We will extend these schemas for our specific inputs.
- **T8/T9 (Downstream)**: The CRUD abstractions must expose async methods for Celery workers (Z_1) and the Memory Router (Z_2).

## 3. High-Level Logic
### 3.1. Database Schemas (SQL)
- `CREATE EXTENSION IF NOT EXISTS vector;`
- **`semantic_memory` table**: stores entity/concept embeddings
  - id (UUID)
  - concept_name (VARCHAR)
  - text_content (TEXT)
  - embedding (VECTOR(1536))
  - metadata (JSONB)
  - created_at (TIMESTAMPTZ)
  - updated_at (TIMESTAMPTZ)
  - **Index**: HNSW index on `embedding vector_cosine_ops` for fast similarity search.
- **`episodic_logs` table**: stores temporal events
  - id (UUID)
  - agent_id (VARCHAR)
  - event_type (VARCHAR)
  - event_content (TEXT)
  - embedding (VECTOR(1536))
  - created_at (TIMESTAMPTZ)
  - **Index**: HNSW index on `embedding vector_cosine_ops`.

### 3.2. CRUD Abstractions (Python)
- Use `asyncpg` combined with `pgvector.asyncpg`.
- Ensure connection pool initialization registers pgvector types (`await register_vector(conn)`) via the pool `init` callback.
- `MemoryDB` class:
  - `async def init_db()`: Run DDL schema creation.
  - `async def store_semantic_memory(data: SemanticMemoryCreate) -> str`
  - `async def search_semantic_memory(query_embedding: List[float], limit: int) -> List[SemanticMemoryRecord]`
  - `async def log_episode(data: EpisodicLogCreate) -> str`
  - `async def search_episodes(query_embedding: List[float], limit: int) -> List[EpisodicLogRecord]`
- Wrap inputs and outputs in Pydantic models inheriting from `BaseContractModel` from T2.
- **Exception Mapping**: Catch `asyncpg` exceptions (e.g. `DataError`, `IntegrityConstraintViolationError`) and re-raise them as a subclass of `ContractViolationError` to respect the API boundaries (no swallowed exceptions).

## 4. Constraints
- Work exclusively within `C:\Users\axton\.gemini\antigravity\scratch\omnimem\sandbox_T5`.
- Do not execute mutating queries on a real database unless isolated (we'll just use a mock or focus on writing the robust abstraction). We will provide an integration script that runs if a PG instance is available.
