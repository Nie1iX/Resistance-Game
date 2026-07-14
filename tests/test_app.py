from resistance.app import create_dispatcher
from resistance.settings_store import SettingsStore


def test_application_dispatcher_includes_language_and_game_routers(tmp_path):
    dispatcher = create_dispatcher(SettingsStore(tmp_path / "bot.db"))

    assert [router.name for router in dispatcher.sub_routers] == ["language", "game"]
