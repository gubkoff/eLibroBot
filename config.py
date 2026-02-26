"""Настройки приложения из переменных окружения и .env."""

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

    # Optional: Google Sheet with category prices (column A = name, column B = price)
    SPREADSHEET_ID: str | None = None
    GOOGLE_CREDENTIALS_FILE: str | None = None


def get_settings() -> Settings:
    return Settings()
