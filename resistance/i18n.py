"""gettext integration and language selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aiogram.enums import ChatType
from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n, I18nMiddleware

if TYPE_CHECKING:
    from resistance.settings_store import SettingsStore


DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = frozenset({"en", "ru"})
I18N = I18n(path=Path(__file__).with_name("locales"), default_locale=DEFAULT_LANGUAGE)


def normalize_language(language: str | None) -> str:
    if language is not None:
        normalized = language.replace("_", "-").split("-", maxsplit=1)[0].lower()
        if normalized in SUPPORTED_LANGUAGES:
            return normalized
    return DEFAULT_LANGUAGE


class LocaleMiddleware(I18nMiddleware):
    def __init__(self, i18n: I18n, store: SettingsStore) -> None:
        super().__init__(i18n)
        self.store = store

    async def get_locale(self, event: TelegramObject, data: dict[str, Any]) -> str:
        del data
        chat = getattr(event, "chat", None)
        if chat is None:
            chat = getattr(getattr(event, "message", None), "chat", None)
        if chat is not None and chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return normalize_language(self.store.chat_language(chat.id))
        user = getattr(event, "from_user", None)
        if user is None:
            return DEFAULT_LANGUAGE
        return normalize_language(self.store.user_language(user.id) or user.language_code)


@dataclass(frozen=True)
class Translator:
    language: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "language", normalize_language(self.language))

    def text(self, key: str, /, **values: object) -> str:
        return I18N.gettext(key, locale=self.language).format(**values)
