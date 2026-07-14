import asyncio
from types import SimpleNamespace

from aiogram.utils.i18n import I18n

from resistance.i18n import LocaleMiddleware, Translator
from resistance.settings_store import SettingsStore


def test_translates_game_messages_and_arguments():
    assert Translator("ru").text("lobby.created") == "Новая игра создана!"
    assert Translator("en").text("lobby.joined", name="Ada") == "Ada joined the lobby."
    assert Translator("ru").text("label.werewolf") == "Оборотень"


def test_falls_back_to_english_for_unknown_language():
    translator = Translator("de")

    assert translator.language == "en"
    assert translator.text("team.confirm") == "Confirm patrol"


def test_translates_three_mission_lobby_setting():
    assert Translator("ru").text("missions.updated", count=3) == "Количество миссий: 3."


def test_locale_middleware_uses_saved_group_language_before_user_language(tmp_path):
    store = SettingsStore(tmp_path / "bot.db")
    store.set_chat_language(-100, "ru")
    middleware = LocaleMiddleware(I18n(path=tmp_path), store)
    event = SimpleNamespace(
        chat=SimpleNamespace(id=-100, type="group"),
        from_user=SimpleNamespace(id=10, language_code="en-US"),
    )

    assert asyncio.run(middleware.get_locale(event, {})) == "ru"


def test_locale_middleware_normalizes_telegram_language_code(tmp_path):
    middleware = LocaleMiddleware(I18n(path=tmp_path), SettingsStore(tmp_path / "bot.db"))
    event = SimpleNamespace(
        chat=SimpleNamespace(id=10, type="private"),
        from_user=SimpleNamespace(id=10, language_code="ru-RU"),
    )

    assert asyncio.run(middleware.get_locale(event, {})) == "ru"
