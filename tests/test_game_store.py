from random import Random

from resistance.domain import JoinResult, MissionCountResult, Player, StartResult
from resistance.game_store import CreateResult, GameStore


def test_store_moves_a_valid_lobby_into_a_match():
    store = GameStore(Random(7))

    assert store.create_lobby(chat_id=-1, initiator_id=1) is CreateResult.CREATED
    for user_id in range(1, 6):
        assert store.join(-1, Player(user_id, str(user_id))) is JoinResult.JOINED

    assert store.start(-1, actor_id=1, is_admin=False) is StartResult.STARTED
    assert store.lobby(-1) is None
    assert store.match(-1) is not None


def test_store_allows_only_one_game_per_group():
    store = GameStore(Random(7))

    assert store.create_lobby(-1, 1) is CreateResult.CREATED
    assert store.create_lobby(-1, 2) is CreateResult.EXISTS
    assert store.cancel(-1)
    assert store.create_lobby(-1, 2) is CreateResult.CREATED


def test_store_carries_selected_mission_count_into_the_match():
    store = GameStore(Random(7))
    assert store.create_lobby(-1, 1) is CreateResult.CREATED
    assert store.set_mission_count(-1, 1, is_admin=False, mission_count=3) is MissionCountResult.UPDATED
    for user_id in range(1, 6):
        store.join(-1, Player(user_id, str(user_id)))

    assert store.start(-1, 1, is_admin=False) is StartResult.STARTED
    match = store.match(-1)
    assert match is not None
    assert match.mission_count == 3
