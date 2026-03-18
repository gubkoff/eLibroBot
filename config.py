"""Настройки приложения из переменных окружения и .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    SOURCE_GROUP_ID: int
    TARGET_GROUP_ID: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
