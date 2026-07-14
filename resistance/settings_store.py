"""Persistent user and group settings."""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from resistance.i18n import SUPPORTED_LANGUAGES


@dataclass(frozen=True)
class SettingsStore:
    database_path: Path

    def __post_init__(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS user_settings "
                "(user_id INTEGER PRIMARY KEY, language TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS chat_settings "
                "(chat_id INTEGER PRIMARY KEY, language TEXT NOT NULL)"
            )

    def set_user_language(self, user_id: int, language: str) -> None:
        self._validate_language(language)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO user_settings(user_id, language) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET language = excluded.language",
                (user_id, language),
            )

    def set_chat_language(self, chat_id: int, language: str) -> None:
        self._validate_language(language)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO chat_settings(chat_id, language) VALUES (?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET language = excluded.language",
                (chat_id, language),
            )

    def user_language(self, user_id: int) -> str | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT language FROM user_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
        return None if row is None else str(row[0])

    def chat_language(self, chat_id: int) -> str | None:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT language FROM chat_settings WHERE chat_id = ?", (chat_id,)
            ).fetchone()
        return None if row is None else str(row[0])

    @staticmethod
    def _validate_language(language: str) -> None:
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
