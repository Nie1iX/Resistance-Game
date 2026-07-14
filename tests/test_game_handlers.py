from random import Random

from resistance.domain import Lobby, Player
from resistance.game import Match
from resistance.game_handlers import GameCallback, _team_keyboard, create_game_router
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


def test_patrol_keyboard_marks_selection_and_enables_confirmation_when_full():
    match = Match.from_lobby(_lobby(), Random(7))
    match.toggle_team_member(match.leader_id, match.turn_order[0])
    match.toggle_team_member(match.leader_id, match.turn_order[1])

    keyboard = _team_keyboard(Translator("en"), match)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]

    assert sum(label.startswith("✓ ") for label in labels) == 2
    assert "Confirm patrol" in labels


def _lobby() -> Lobby:
    lobby = Lobby(chat_id=-1, initiator_id=1)
    for user_id in range(1, 6):
        lobby.join(Player(user_id, str(user_id)))
    return lobby
