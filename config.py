"""Настройки приложения из переменных окружения и .env."""

from functools import lru_cache

from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    # Backward-compatible single source chat id.
    # Can be either a single integer (or its string form) or a comma-separated list (legacy-friendly).
    SOURCE_GROUP_ID: Optional[str] = None
    # Optional: comma-separated list of chat ids, e.g. "-1001,-1002".
    SOURCE_GROUP_IDS: Optional[str] = None
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

    @field_validator("TARGET_GROUP_ID")
    @classmethod
    def _validate_group_id(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return None
        if v == 0:
            raise ValueError("Group id must be non-zero")
        return v

    @field_validator("SOURCE_GROUP_ID")
    @classmethod
    def _validate_source_group_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("SOURCE_GROUP_IDS")
    @classmethod
    def _validate_source_group_ids(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _validate_groups_not_equal(self) -> "Settings":
        src_ids = self.source_group_ids
        if not src_ids:
            raise ValueError("Either SOURCE_GROUP_ID or SOURCE_GROUP_IDS must be set")
        if self.TARGET_GROUP_ID in src_ids:
            raise ValueError("TARGET_GROUP_ID must differ from SOURCE_GROUP_ID(S)")
        return self

    @property
    def source_group_ids(self) -> tuple[int, ...]:
        """
        Source chat ids as a tuple.

        Priority:
        - SOURCE_GROUP_IDS (comma/space-separated) if set
        - SOURCE_GROUP_ID otherwise
        """
        raw = self.SOURCE_GROUP_IDS or self.SOURCE_GROUP_ID
        if not raw:
            return tuple()
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
        out: list[int] = []
        for p in parts:
            if not p:
                continue
            try:
                n = int(p)
            except ValueError as exc:
                raise ValueError(f"Invalid SOURCE_GROUP_ID(S) element: {p!r}") from exc
            if n == 0:
                raise ValueError("Group id must be non-zero")
            out.append(n)
        # De-duplicate but preserve order
        seen: set[int] = set()
        uniq = [x for x in out if not (x in seen or seen.add(x))]
        return tuple(uniq)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
