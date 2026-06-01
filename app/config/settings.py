from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "twitter-scraper-api"
    OUTPUT_DIR: str = "output"
    REQUIRE_API_KEY: bool = False
    API_KEY: str | None = None
    DEFAULT_LIMIT_PER_CATEGORY: int = Field(default=1000, ge=1, le=10000)
    SAFE_DELAY_SECONDS: float = Field(default=1.0, ge=0.0)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def output_path(self) -> Path:
        return Path(self.OUTPUT_DIR)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
