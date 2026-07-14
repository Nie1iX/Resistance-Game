from resistance.handlers import LanguageSelection, create_router, language_keyboard
from resistance.settings_store import SettingsStore


def test_language_keyboard_encodes_scope_and_language():
    keyboard = language_keyboard("user")
    callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert LanguageSelection.unpack(callbacks[0]).scope == "user"
    assert {LanguageSelection.unpack(callback).language for callback in callbacks} == {"en", "ru"}


def test_language_router_can_be_constructed(tmp_path):
    router = create_router(SettingsStore(tmp_path / "bot.db"))

    assert router.name == "language"
