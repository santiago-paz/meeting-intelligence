from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Environment variables win over api/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Ingest needs it for context headers; without it POST /meetings answers 503.
    anthropic_api_key: str | None = None
    # Named so a stray ANTHROPIC_BASE_URL in the host environment cannot bind
    # to it; the SDK is always given this value explicitly.
    claude_base_url: str = "https://api.anthropic.com"
    context_header_model: str = "claude-haiku-4-5"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
