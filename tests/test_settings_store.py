import pytest

from resistance.settings_store import SettingsStore


def test_user_language_is_independent_of_group_language(tmp_path):
    store = SettingsStore(tmp_path / "bot.db")
    store.set_user_language(10, "ru")
    store.set_chat_language(-20, "en")

    assert store.user_language(10) == "ru"
    assert store.chat_language(-20) == "en"
    assert store.user_language(11) is None
    assert store.chat_language(-21) is None


def test_rejects_unsupported_language(tmp_path):
    store = SettingsStore(tmp_path / "bot.db")

    with pytest.raises(ValueError, match="Unsupported language"):
        store.set_user_language(10, "de")
