"""Application configuration loaded from environment variables."""

import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://writer:writer@localhost:5432/writer"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    chroma_path: str = "./data/chroma"
    undo_buffer_size: int = 1000
    dev_seed_doc: bool = False

    @field_validator("undo_buffer_size", mode="before")
    @classmethod
    def validate_buffer_size(cls, v: object) -> int:
        try:
            n = int(str(v))
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass
        logger.warning("Invalid UNDO_BUFFER_SIZE value %r; falling back to 1000", v)
        return 1000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "env_ignore_empty": True,
        "extra": "ignore",
    }


settings = Settings()
