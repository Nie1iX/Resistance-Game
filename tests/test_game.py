from random import Random

import pytest

from resistance.domain import GameVariant, Lobby, Player
from resistance.game import Match, MissionResult, Phase, Role, TeamVoteResult


@pytest.mark.parametrize(
    ("player_count", "villagers", "werewolves"),
    [(5, 3, 2), (6, 4, 2), (7, 4, 3), (8, 5, 3), (9, 6, 3), (10, 6, 4)],
)
def test_match_assigns_the_official_role_distribution(player_count, villagers, werewolves):
    match = Match.from_lobby(_lobby(player_count), Random(7))

    roles = [player.role for player in match.players.values()]
    assert roles.count(Role.VILLAGER) == villagers
    assert roles.count(Role.WEREWOLF) == werewolves
    assert match.phase is Phase.BUILD_TEAM


@pytest.mark.parametrize(
    ("player_count", "team_sizes"),
    [
        (5, (2, 3, 2, 3, 3)),
        (6, (2, 3, 4, 3, 4)),
        (7, (2, 3, 3, 4, 4)),
        (8, (3, 4, 4, 5, 5)),
        (9, (3, 4, 4, 5, 5)),
        (10, (3, 4, 4, 5, 5)),
    ],
)
def test_uses_the_official_mission_team_sizes(player_count, team_sizes):
    match = Match.from_lobby(_lobby(player_count), Random(7))

    assert match.team_sizes == team_sizes
    for mission_index, size in enumerate(team_sizes):
        match.mission_index = mission_index
        assert match.required_team_size == size


def test_leader_builds_exactly_the_required_team():
    match = Match.from_lobby(_lobby(5), Random(7))
    leader_id = match.leader_id

    match.toggle_team_member(leader_id, match.turn_order[0])
    with pytest.raises(ValueError, match="exactly"):
        match.propose_team(leader_id)

    match.toggle_team_member(leader_id, match.turn_order[1])
    match.propose_team(leader_id)

    assert match.phase is Phase.TEAM_VOTE
    assert match.proposed_team == match.turn_order[:2]
    assert match.team_votes == {}


def test_team_requires_a_strict_majority_and_rejection_rotates_leader():
    match = _proposed_match(6)
    old_leader_id = match.leader_id

    results = [match.vote_team(user_id, user_id <= 3) for user_id in match.turn_order]

    assert results[-1] is TeamVoteResult.REJECTED
    assert match.phase is Phase.BUILD_TEAM
    assert match.rejected_teams == 1
    assert match.leader_id != old_leader_id


def test_fifth_rejected_team_ends_the_game_for_werewolves():
    match = _proposed_match(5)
    match.rejected_teams = 4

    for user_id in match.turn_order:
        result = match.vote_team(user_id, approve=False)

    assert result is TeamVoteResult.REJECTED
    assert match.phase is Phase.FINISHED
    assert match.winner is Role.WEREWOLF


def test_approved_team_moves_to_secret_patrol_vote():
    match = _proposed_match(5)

    for user_id in match.turn_order:
        result = match.vote_team(user_id, approve=True)

    assert result is TeamVoteResult.APPROVED
    assert match.phase is Phase.MISSION
    assert match.mission_votes == {}


def test_villager_cannot_sabotage_a_mission():
    match = _mission_match(5)
    villager_id = next(
        user_id
        for user_id in match.proposed_team or []
        if match.players[user_id].role is Role.VILLAGER
    )

    with pytest.raises(ValueError, match="Villagers"):
        match.vote_mission(villager_id, success=False)


def test_fourth_mission_with_seven_players_needs_two_sabotages_to_fail():
    match = Match.from_lobby(_lobby(7), Random(7))
    match.mission_index = 3
    werewolves = [user_id for user_id, player in match.players.items() if player.role is Role.WEREWOLF]
    villagers = [user_id for user_id, player in match.players.items() if player.role is Role.VILLAGER]
    team = [werewolves[0], *villagers[:3]]
    match.proposed_team = team
    match.phase = Phase.MISSION
    match.mission_votes = {}

    for user_id in team:
        result = match.vote_mission(user_id, success=user_id != werewolves[0])

    assert result is MissionResult.SUCCESS
    assert match.successful_missions == 1
    assert match.last_sabotages == 1


def test_three_successful_missions_end_the_game_for_villagers():
    match = _mission_match(5)
    match.successful_missions = 2

    for user_id in match.proposed_team or []:
        result = match.vote_mission(user_id, success=True)

    assert result is MissionResult.SUCCESS
    assert match.phase is Phase.FINISHED
    assert match.winner is Role.VILLAGER


def test_three_mission_game_ends_after_two_wins():
    lobby = _lobby(5)
    lobby.mission_count = 3
    match = Match.from_lobby(lobby, Random(7))
    match.successful_missions = 1
    match.proposed_team = match.turn_order[: match.required_team_size]
    match.phase = Phase.MISSION
    match.mission_votes = {}

    for user_id in match.proposed_team:
        result = match.vote_mission(user_id, success=True)

    assert result is MissionResult.SUCCESS
    assert match.wins_required == 2
    assert match.phase is Phase.FINISHED
    assert match.winner is Role.VILLAGER


def test_werewolf_variant_uses_the_original_nine_player_role_distribution():
    match = Match.from_lobby(_lobby(9, GameVariant.WEREWOLVES), Random(7))

    roles = [player.role for player in match.players.values()]
    assert roles.count(Role.VILLAGER) == 5
    assert roles.count(Role.WEREWOLF) == 4


@pytest.mark.parametrize(
    ("player_count", "team_sizes"),
    [(5, (2, 3, 3)), (6, (2, 3, 4)), (8, (3, 4, 5))],
)
def test_werewolf_variant_grows_the_team_after_successes(player_count, team_sizes):
    match = Match.from_lobby(_lobby(player_count, GameVariant.WEREWOLVES), Random(7))

    for successes, expected_size in enumerate(team_sizes):
        match.successful_missions = successes
        assert match.required_team_size == expected_size


def test_werewolf_variant_does_not_end_after_five_rejected_teams():
    match = _proposed_match(5, GameVariant.WEREWOLVES)
    match.rejected_teams = 4

    for user_id in match.turn_order:
        result = match.vote_team(user_id, approve=False)

    assert result is TeamVoteResult.REJECTED
    assert match.phase is Phase.BUILD_TEAM
    assert match.winner is None
    assert match.rejected_teams == 5


def test_werewolf_variant_ends_after_three_attacks():
    match = Match.from_lobby(_lobby(5, GameVariant.WEREWOLVES), Random(7))
    werewolf_id = next(
        user_id for user_id, player in match.players.items() if player.role is Role.WEREWOLF
    )
    teammate_id = next(user_id for user_id in match.players if user_id != werewolf_id)
    match.failed_missions = 2
    match.proposed_team = [werewolf_id, teammate_id]
    match.phase = Phase.MISSION
    match.mission_votes = {}

    match.vote_mission(werewolf_id, success=False)
    result = match.vote_mission(teammate_id, success=True)

    assert result is MissionResult.FAILED
    assert match.phase is Phase.FINISHED
    assert match.winner is Role.WEREWOLF
    assert match.required_sabotages == 1
    assert match.wins_required == 3


def _lobby(
    players: int, variant: GameVariant = GameVariant.CLASSIC
) -> Lobby:
    lobby = Lobby(chat_id=-1, initiator_id=1, variant=variant)
    for user_id in range(1, players + 1):
        lobby.join(Player(user_id, str(user_id)))
    return lobby


def _proposed_match(
    players: int, variant: GameVariant = GameVariant.CLASSIC
) -> Match:
    match = Match.from_lobby(_lobby(players, variant), Random(7))
    for user_id in match.turn_order[: match.required_team_size]:
        match.toggle_team_member(match.leader_id, user_id)
    match.propose_team(match.leader_id)
    return match


def _mission_match(players: int) -> Match:
    match = _proposed_match(players)
    for user_id in match.turn_order:
        match.vote_team(user_id, approve=True)
    return match
