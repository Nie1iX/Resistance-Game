"""Rules engine for the supported Resistance game variants."""

from dataclasses import dataclass, field
from enum import Enum, auto
from random import Random
from uuid import uuid4

from resistance.domain import GameVariant, Lobby


class Role(str, Enum):
    VILLAGER = "villager"
    WEREWOLF = "werewolf"


class Phase(Enum):
    BUILD_TEAM = auto()
    TEAM_VOTE = auto()
    MISSION = auto()
    FINISHED = auto()


class TeamVoteResult(Enum):
    PENDING = auto()
    APPROVED = auto()
    REJECTED = auto()


class MissionResult(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


_CLASSIC_ROLE_SETS: dict[int, tuple[Role, ...]] = {
    5: (Role.VILLAGER,) * 3 + (Role.WEREWOLF,) * 2,
    6: (Role.VILLAGER,) * 4 + (Role.WEREWOLF,) * 2,
    7: (Role.VILLAGER,) * 4 + (Role.WEREWOLF,) * 3,
    8: (Role.VILLAGER,) * 5 + (Role.WEREWOLF,) * 3,
    9: (Role.VILLAGER,) * 6 + (Role.WEREWOLF,) * 3,
    10: (Role.VILLAGER,) * 6 + (Role.WEREWOLF,) * 4,
}

_WEREWOLF_ROLE_SETS = {
    **_CLASSIC_ROLE_SETS,
    9: (Role.VILLAGER,) * 5 + (Role.WEREWOLF,) * 4,
}

_TEAM_SIZES: dict[int, tuple[int, ...]] = {
    5: (2, 3, 2, 3, 3),
    6: (2, 3, 4, 3, 4),
    7: (2, 3, 3, 4, 4),
    8: (3, 4, 4, 5, 5),
    9: (3, 4, 4, 5, 5),
    10: (3, 4, 4, 5, 5),
}


@dataclass(frozen=True)
class GamePlayer:
    user_id: int
    name: str
    role: Role


@dataclass
class Match:
    chat_id: int
    initiator_id: int
    players: dict[int, GamePlayer]
    turn_order: list[int]
    phase: Phase
    variant: GameVariant = GameVariant.CLASSIC
    mission_count: int = 5
    match_id: str = field(default_factory=lambda: uuid4().hex)
    leader_index: int = 0
    mission_index: int = 0
    successful_missions: int = 0
    failed_missions: int = 0
    rejected_teams: int = 0
    selected_team: list[int] = field(default_factory=list)
    proposed_team: list[int] | None = None
    team_votes: dict[int, bool] | None = None
    mission_votes: dict[int, bool] | None = None
    mission_results: list[MissionResult] = field(default_factory=list)
    last_sabotages: int = 0
    winner: Role | None = None

    @classmethod
    def from_lobby(cls, lobby: Lobby, random: Random) -> "Match":
        role_sets = (
            _CLASSIC_ROLE_SETS
            if lobby.variant is GameVariant.CLASSIC
            else _WEREWOLF_ROLE_SETS
        )
        roles = list(role_sets[len(lobby.players)])
        random.shuffle(roles)
        players = {
            user_id: GamePlayer(user_id, player.name, roles.pop())
            for user_id, player in lobby.players.items()
        }
        turn_order = list(players)
        random.shuffle(turn_order)
        return cls(
            chat_id=lobby.chat_id,
            initiator_id=lobby.initiator_id,
            players=players,
            turn_order=turn_order,
            phase=Phase.BUILD_TEAM,
            variant=lobby.variant,
            mission_count=lobby.mission_count,
        )

    @property
    def leader_id(self) -> int:
        return self.turn_order[self.leader_index]

    @property
    def team_sizes(self) -> tuple[int, ...]:
        if self.variant is GameVariant.WEREWOLVES:
            if len(self.players) == 5:
                return (2, 3, 3)
            if len(self.players) <= 7:
                return (2, 3, 4)
            return (3, 4, 5)
        return _TEAM_SIZES[len(self.players)]

    @property
    def required_team_size(self) -> int:
        if self.variant is GameVariant.WEREWOLVES:
            return self.team_sizes[min(self.successful_missions, 2)]
        return self.team_sizes[self.mission_index]

    @property
    def required_sabotages(self) -> int:
        if self.variant is GameVariant.WEREWOLVES:
            return 1
        return 2 if len(self.players) >= 7 and self.mission_index == 3 else 1

    @property
    def wins_required(self) -> int:
        if self.variant is GameVariant.WEREWOLVES:
            return 3
        return self.mission_count // 2 + 1

    def toggle_team_member(self, actor_id: int, candidate_id: int) -> None:
        if self.phase is not Phase.BUILD_TEAM or actor_id != self.leader_id:
            raise ValueError("Only the current leader can build a team")
        if candidate_id not in self.players:
            raise ValueError("Unknown team member")
        if candidate_id in self.selected_team:
            self.selected_team.remove(candidate_id)
            return
        if len(self.selected_team) == self.required_team_size:
            raise ValueError("The team already has the required number of members")
        self.selected_team.append(candidate_id)

    def propose_team(self, actor_id: int) -> None:
        if self.phase is not Phase.BUILD_TEAM or actor_id != self.leader_id:
            raise ValueError("Only the current leader can propose a team")
        if len(self.selected_team) != self.required_team_size:
            raise ValueError(f"Select exactly {self.required_team_size} team members")
        self.proposed_team = list(self.selected_team)
        self.team_votes = {}
        self.phase = Phase.TEAM_VOTE

    def vote_team(self, actor_id: int, approve: bool) -> TeamVoteResult:
        if self.phase is not Phase.TEAM_VOTE or actor_id not in self.players:
            raise ValueError("This player cannot vote now")
        assert self.team_votes is not None
        if actor_id in self.team_votes:
            raise ValueError("This player has already voted")
        self.team_votes[actor_id] = approve
        if len(self.team_votes) < len(self.players):
            return TeamVoteResult.PENDING
        if sum(self.team_votes.values()) * 2 > len(self.players):
            self.mission_votes = {}
            self.phase = Phase.MISSION
            return TeamVoteResult.APPROVED
        self.rejected_teams += 1
        if self.variant is GameVariant.CLASSIC and self.rejected_teams == 5:
            self.winner = Role.WEREWOLF
            self.phase = Phase.FINISHED
        else:
            self._advance_leader()
            self.selected_team = []
            self.proposed_team = None
            self.phase = Phase.BUILD_TEAM
        return TeamVoteResult.REJECTED

    def vote_mission(self, actor_id: int, success: bool) -> MissionResult:
        if self.phase is not Phase.MISSION or self.proposed_team is None or actor_id not in self.proposed_team:
            raise ValueError("This player is not on the current team")
        if not success and self.players[actor_id].role is Role.VILLAGER:
            raise ValueError("Villagers cannot sabotage a patrol")
        assert self.mission_votes is not None
        if actor_id in self.mission_votes:
            raise ValueError("This player has already voted")
        self.mission_votes[actor_id] = success
        if len(self.mission_votes) < len(self.proposed_team):
            return MissionResult.PENDING

        self.last_sabotages = sum(not vote for vote in self.mission_votes.values())
        result = (
            MissionResult.FAILED
            if self.last_sabotages >= self.required_sabotages
            else MissionResult.SUCCESS
        )
        self.mission_results.append(result)
        if result is MissionResult.SUCCESS:
            self.successful_missions += 1
            if self.successful_missions == self.wins_required:
                self.winner = Role.VILLAGER
        else:
            self.failed_missions += 1
            if self.failed_missions == self.wins_required:
                self.winner = Role.WEREWOLF
        if self.winner is not None:
            self.phase = Phase.FINISHED
            return result

        self.mission_index += 1
        self.rejected_teams = 0
        self._advance_leader()
        self.selected_team = []
        self.proposed_team = None
        self.phase = Phase.BUILD_TEAM
        return result

    def _advance_leader(self) -> None:
        self.leader_index = (self.leader_index + 1) % len(self.turn_order)
