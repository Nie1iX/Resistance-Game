from random import Random

from resistance.domain import GameVariant, Lobby, Player
from resistance.game import Match, Role
from resistance.game_handlers import (
    GameCallback,
    _board,
    _label,
    _lobby_keyboard,
    _main_menu_keyboard,
    _team_keyboard,
    create_game_router,
)
from resistance.game_store import GameStore
from resistance.i18n import Translator
from resistance.settings_store import SettingsStore
from resistance.statistics_store import StatisticsStore


def test_game_router_can_be_constructed(tmp_path):
    database_path = tmp_path / "bot.db"
    router = create_game_router(
        GameStore(Random(7)), SettingsStore(database_path), StatisticsStore(database_path)
    )

    assert router.name == "game"


def test_game_callback_keeps_group_identity_for_private_messages():
    callback = GameCallback(chat_id=-100, operation="team_vote", value="yes")

    assert GameCallback.unpack(callback.pack()).chat_id == -100


def test_team_keyboard_marks_selection_and_enables_confirmation_when_full():
    match = Match.from_lobby(_lobby(), Random(7))
    match.toggle_team_member(match.leader_id, match.turn_order[0])
    match.toggle_team_member(match.leader_id, match.turn_order[1])

    keyboard = _team_keyboard(Translator("en"), match)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert sum(label.startswith("✓ ") for label in labels) == 2
    assert "Confirm team" in labels


def test_main_menu_opens_lobby_creation():
    keyboard = _main_menu_keyboard(Translator("en"), chat_id=-100)
    button = keyboard.inline_keyboard[0][0]

    assert button.text == "Create game"
    assert GameCallback.unpack(button.callback_data).operation == "lobby_create"


def test_lobby_keyboard_covers_setup_without_extra_commands():
    lobby = _lobby()
    lobby.mission_count = 3

    keyboard = _lobby_keyboard(Translator("en"), lobby)
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    labels = [button.text for button in buttons]
    operations = {GameCallback.unpack(button.callback_data).operation for button in buttons}

    assert labels == [
        "Join game",
        "✓ Classic",
        "Werewolves",
        "✓ 3 missions",
        "5 missions",
        "Start game",
        "Cancel game",
    ]
    assert operations == {
        "lobby_join",
        "lobby_variant",
        "lobby_missions",
        "lobby_start",
        "lobby_cancel",
    }


def test_werewolf_lobby_hides_classic_mission_count_buttons():
    lobby = _lobby()
    lobby.variant = GameVariant.WEREWOLVES

    keyboard = _lobby_keyboard(Translator("en"), lobby)
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    labels = [button.text for button in buttons]
    operations = {GameCallback.unpack(button.callback_data).operation for button in buttons}

    assert labels == ["Join game", "Classic", "✓ Werewolves", "Start game", "Cancel game"]
    assert "lobby_missions" not in operations


def test_variant_controls_role_labels_and_board_summary():
    translator = Translator("en")
    match = Match.from_lobby(_lobby(), Random(7))

    assert _label(translator, GameVariant.CLASSIC, Role.VILLAGER) == "Resistance member"
    assert _label(translator, GameVariant.CLASSIC, Role.WEREWOLF) == "Spy"

    match.variant = GameVariant.WEREWOLVES
    assert _label(translator, match.variant, Role.VILLAGER) == "Villager"
    assert _label(translator, match.variant, Role.WEREWOLF) == "Werewolf"
    assert "Curses remaining: 3" in _board(translator, match)
    assert "Village health: 3" in _board(translator, match)


def test_game_router_registers_lobby_button_actions(tmp_path):
    database_path = tmp_path / "bot.db"
    router = create_game_router(
        GameStore(Random(7)), SettingsStore(database_path), StatisticsStore(database_path)
    )

    callbacks = {handler.callback.__name__ for handler in router.callback_query.handlers}

    assert {
        "lobby_create",
        "lobby_join",
        "lobby_variant",
        "lobby_missions",
        "lobby_start",
        "lobby_cancel",
    } <= callbacks


def _lobby() -> Lobby:
    lobby = Lobby(chat_id=-1, initiator_id=1)
    for user_id in range(1, 6):
        lobby.join(Player(user_id, str(user_id)))
    return lobby
