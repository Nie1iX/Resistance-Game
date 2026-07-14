from resistance.domain import JoinResult, Lobby, MissionCountResult, Player, StartResult


def test_lobby_accepts_between_five_and_ten_unique_players():
    lobby = Lobby(chat_id=-1, initiator_id=1)

    assert lobby.join(Player(2, "Ada")) is JoinResult.JOINED
    assert lobby.join(Player(2, "Ada")) is JoinResult.ALREADY_JOINED

    for user_id in range(3, 12):
        assert lobby.join(Player(user_id, str(user_id))) is JoinResult.JOINED

    assert lobby.join(Player(12, "Grace")) is JoinResult.FULL
    assert lobby.can_start


def test_only_initiator_or_admin_can_start_a_lobby():
    lobby = _lobby(5)

    assert lobby.start(actor_id=2, is_admin=False) is StartResult.UNAUTHORIZED
    assert lobby.start(actor_id=2, is_admin=True) is StartResult.STARTED
    assert lobby.started


def test_lobby_creator_can_choose_three_or_five_missions_before_start():
    lobby = Lobby(chat_id=-1, initiator_id=1)

    assert lobby.mission_count == 5
    assert lobby.set_mission_count(1, is_admin=False, mission_count=3) is MissionCountResult.UPDATED
    assert lobby.mission_count == 3
    assert lobby.set_mission_count(2, is_admin=False, mission_count=5) is MissionCountResult.UNAUTHORIZED
    assert lobby.set_mission_count(1, is_admin=False, mission_count=4) is MissionCountResult.INVALID


def _lobby(players: int) -> Lobby:
    lobby = Lobby(chat_id=-1, initiator_id=1)
    for user_id in range(1, players + 1):
        lobby.join(Player(user_id, str(user_id)))
    return lobby
