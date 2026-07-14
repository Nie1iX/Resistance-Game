"""Runtime configuration."""

from dataclasses import dataclass
from os import getenv
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: Path


def load_settings() -> Settings:
    bot_token = getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN must be set")
    return Settings(
        bot_token=bot_token,
        database_path=Path(getenv("DATABASE_PATH", "resistance.db")),
    )
