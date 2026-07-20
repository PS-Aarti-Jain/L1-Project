import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base Directory of the backend
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # API Keys & Auth
    GEMINI_API_KEY: str = Field(default="", validation_alias="GEMINI_API_KEY")
    ANTHROPIC_API_KEY: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    
    # GitHub Integration (MCP)
    GITHUB_PAT: str = Field(default="", validation_alias="GITHUB_PAT")
    GITHUB_REPOSITORY: str = Field(default="owner/repo", validation_alias="GITHUB_REPOSITORY")
    
    # App Settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    SECRET_KEY: str = Field(default="devassist-super-secret-key-change-in-prod", validation_alias="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # RAG Settings
    CHROMA_DB_DIR: str = Field(default=str(BASE_DIR / "chroma_db"))
    QDRANT_DB_DIR: str = Field(default=str(BASE_DIR / "qdrant_db"))
    DOCS_DIR: str = Field(default=str(BASE_DIR.parent / "docs"))
    
    # Model settings
    LLM_PROVIDER: str = "gemini"  # 'gemini', 'anthropic', or 'ollama'
    DEFAULT_GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    DEFAULT_ANTHROPIC_MODEL: str = "claude-3-5-sonnet-latest"

    # Embedding settings
    EMBEDDING_PROVIDER: str = "fastembed"  # 'fastembed', 'sentence-transformers', 'gemini', 'ollama'
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # or 'all-MiniLM-L6-v2', 'text-embedding-004'
    RELEVANCE_THRESHOLD: float = 0.45

    # Ollama settings (local, free, no API key needed)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # OpenRouter settings
    OPENROUTER_API_KEY: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"

    # Prompt settings
    SYSTEM_PROMPT_PATH: str = Field(default=str(BASE_DIR / "prompts" / "system_prompt.txt"))
    QUERY_REWRITE_PROMPT_PATH: str = Field(default=str(BASE_DIR / "prompts" / "query_rewrite_prompt.txt"))

    
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
