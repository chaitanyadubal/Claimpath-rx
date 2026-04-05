from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    neo4j_uri: str = Field("bolt://localhost:7687", env="NEO4J_URI")
    neo4j_username: str = Field("neo4j", env="NEO4J_USERNAME")
    neo4j_password: str = Field("password", env="NEO4J_PASSWORD")

    qdrant_url: str = Field("http://localhost:6333", env="QDRANT_URL")
    qdrant_api_key: str = Field("", env="QDRANT_API_KEY")
    collection_name: str = Field("med_policy_chunks", env="COLLECTION_NAME")

    groq_api_key: str = Field("", env="GROQ_API_KEY")
    llm_model: str = Field("llama-3.3-70b-versatile", env="LLM_MODEL")

    embedding_model: str = Field("BAAI/bge-m3", env="EMBEDDING_MODEL")
    embedding_dim: int = 1024

    cache_ttl_seconds: int = Field(3600, env="CACHE_TTL_SECONDS")
    cache_max_size: int = Field(500, env="CACHE_MAX_SIZE")

    app_env: str = Field("development", env="APP_ENV")

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
