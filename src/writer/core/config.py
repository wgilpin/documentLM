"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://writer:writer@localhost:5432/writer"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_ignore_empty": True,
        "extra": "ignore",
    }


settings = Settings()
