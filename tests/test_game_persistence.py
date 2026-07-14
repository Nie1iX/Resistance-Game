from random import Random

from resistance.domain import GameVariant, JoinResult, Player, StartResult
from resistance.game import Phase
from resistance.game_persistence import GamePersistence
from resistance.game_store import CreateResult, GameStore


def test_restores_a_pending_lobby_after_a_process_restart(tmp_path):
    database_path = tmp_path / "bot.db"
    store = GameStore(Random(7), GamePersistence(database_path))
    assert store.create_lobby(-1, 1) is CreateResult.CREATED
    assert store.join(-1, Player(1, "Ada")) is JoinResult.JOINED

    restored = GameStore(Random(99), GamePersistence(database_path)).lobby(-1)

    assert restored is not None
    assert restored.initiator_id == 1
    assert restored.players == {1: Player(1, "Ada")}


def test_restores_selected_mission_count_for_lobby_and_match(tmp_path):
    database_path = tmp_path / "bot.db"
    store = GameStore(Random(7), GamePersistence(database_path))
    store.create_lobby(-1, 1)
    store.set_mission_count(-1, 1, is_admin=False, mission_count=3)
    for user_id in range(1, 6):
        store.join(-1, Player(user_id, str(user_id)))

    lobby = GameStore(Random(99), GamePersistence(database_path)).lobby(-1)
    assert lobby is not None
    assert lobby.mission_count == 3

    store.start(-1, 1, is_admin=False)
    match = GameStore(Random(99), GamePersistence(database_path)).match(-1)
    assert match is not None
    assert match.mission_count == 3


def test_restores_selected_variant_for_lobby_and_match(tmp_path):
    database_path = tmp_path / "bot.db"
    store = GameStore(Random(7), GamePersistence(database_path))
    store.create_lobby(-1, 1)
    store.set_variant(-1, 1, False, GameVariant.WEREWOLVES)
    for user_id in range(1, 6):
        store.join(-1, Player(user_id, str(user_id)))

    lobby = GameStore(Random(99), GamePersistence(database_path)).lobby(-1)
    assert lobby is not None
    assert lobby.variant is GameVariant.WEREWOLVES

    store.start(-1, 1, is_admin=False)
    match = GameStore(Random(99), GamePersistence(database_path)).match(-1)
    assert match is not None
    assert match.variant is GameVariant.WEREWOLVES


def test_restores_team_selection_and_votes_after_a_process_restart(tmp_path):
    database_path = tmp_path / "bot.db"
    store = _started_store(database_path)
    match = store.match(-1)
    assert match is not None
    for user_id in match.turn_order[: match.required_team_size]:
        match.toggle_team_member(match.leader_id, user_id)
    match.propose_team(match.leader_id)
    match.vote_team(match.turn_order[0], approve=True)
    store.save(match.chat_id)

    restored = GameStore(Random(99), GamePersistence(database_path)).match(-1)

    assert restored is not None
    assert restored.phase is Phase.TEAM_VOTE
    assert restored.match_id == match.match_id
    assert restored.proposed_team == match.proposed_team
    assert restored.team_votes == {match.turn_order[0]: True}
    assert {user_id: player.role for user_id, player in restored.players.items()} == {
        user_id: player.role for user_id, player in match.players.items()
    }


def test_restores_partial_secret_mission_vote(tmp_path):
    database_path = tmp_path / "bot.db"
    store = _started_store(database_path)
    match = store.match(-1)
    assert match is not None
    for user_id in match.turn_order[: match.required_team_size]:
        match.toggle_team_member(match.leader_id, user_id)
    match.propose_team(match.leader_id)
    for user_id in match.turn_order:
        match.vote_team(user_id, approve=True)
    assert match.proposed_team is not None
    voter_id = match.proposed_team[0]
    match.vote_mission(voter_id, success=True)
    store.save(match.chat_id)

    restored = GameStore(Random(99), GamePersistence(database_path)).match(-1)

    assert restored is not None
    assert restored.phase is Phase.MISSION
    assert restored.mission_votes == {voter_id: True}


def _started_store(database_path):
    store = GameStore(Random(7), GamePersistence(database_path))
    assert store.create_lobby(-1, 1) is CreateResult.CREATED
    for user_id in range(1, 6):
        assert store.join(-1, Player(user_id, str(user_id))) is JoinResult.JOINED
    assert store.start(-1, actor_id=1, is_admin=False) is StartResult.STARTED
    return store
