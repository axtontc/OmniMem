from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database Settings
    POSTGRES_USER: str = "omnimem"
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_DB: str = "omnimem_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    
    # Neo4j Settings
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = Field(default="")
    NEO4J_URI: str = "bolt://localhost:7687"
    
    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Celery Settings
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

def get_postgres_uri() -> str:
    return f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
