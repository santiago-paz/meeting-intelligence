from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Environment variables win over api/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
