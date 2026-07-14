from random import Random

from resistance.domain import Lobby, Player
from resistance.game import Match, Phase, Role
from resistance.statistics_store import ChatStatistics, PlayerStatistics, StatisticsStore


def test_records_one_finished_match_and_returns_group_and_player_totals(tmp_path):
    match = _finished_match()
    winner = next(player for player in match.players.values() if player.role is Role.VILLAGER)
    store = StatisticsStore(tmp_path / "bot.db")

    assert store.record(match) is True
    assert store.record(match) is False

    assert store.player_statistics(match.chat_id, winner.user_id) == PlayerStatistics(games=1, wins=1)
    assert store.chat_statistics(match.chat_id) == ChatStatistics(
        games=1, villager_wins=1, werewolf_wins=0
    )


def _finished_match() -> Match:
    lobby = Lobby(chat_id=-1, initiator_id=1)
    for user_id in range(1, 6):
        lobby.join(Player(user_id, str(user_id)))
    match = Match.from_lobby(lobby, Random(7))
    match.phase = Phase.FINISHED
    match.winner = Role.VILLAGER
    return match
