"""Настройки приложения из переменных окружения и .env."""

from functools import lru_cache

from pydantic import field_validator, model_validator
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

    @field_validator("BOT_TOKEN")
    @classmethod
    def _validate_bot_token(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("BOT_TOKEN is empty")
        # Telegram bot token is typically "digits:secret"; avoid strict regex to not block future formats.
        if len(v) < 20:
            raise ValueError("BOT_TOKEN looks too short")
        return v

    @field_validator("SOURCE_GROUP_ID", "TARGET_GROUP_ID")
    @classmethod
    def _validate_group_id(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Group id must be non-zero")
        return v

    @model_validator(mode="after")
    def _validate_groups_not_equal(self) -> "Settings":
        if self.SOURCE_GROUP_ID == self.TARGET_GROUP_ID:
            raise ValueError("SOURCE_GROUP_ID must differ from TARGET_GROUP_ID")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
