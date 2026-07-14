"""Telegram-independent lobby state."""

from dataclasses import dataclass, field
from enum import Enum, auto


MIN_PLAYERS = 5
MAX_PLAYERS = 10


class JoinResult(Enum):
    JOINED = auto()
    ALREADY_JOINED = auto()
    FULL = auto()
    STARTED = auto()
    MISSING = auto()


class StartResult(Enum):
    STARTED = auto()
    UNAUTHORIZED = auto()
    TOO_FEW_PLAYERS = auto()
    MISSING = auto()


class MissionCountResult(Enum):
    UPDATED = auto()
    UNAUTHORIZED = auto()
    INVALID = auto()
    STARTED = auto()
    MISSING = auto()


class GameVariant(str, Enum):
    CLASSIC = "classic"
    WEREWOLVES = "werewolves"


class VariantResult(Enum):
    UPDATED = auto()
    UNAUTHORIZED = auto()
    STARTED = auto()
    MISSING = auto()


@dataclass(frozen=True)
class Player:
    user_id: int
    name: str


@dataclass
class Lobby:
    chat_id: int
    initiator_id: int
    mission_count: int = 5
    variant: GameVariant = GameVariant.CLASSIC
    players: dict[int, Player] = field(default_factory=dict)
    started: bool = False

    @property
    def can_start(self) -> bool:
        return MIN_PLAYERS <= len(self.players) <= MAX_PLAYERS

    def join(self, player: Player) -> JoinResult:
        if self.started:
            return JoinResult.STARTED
        if player.user_id in self.players:
            return JoinResult.ALREADY_JOINED
        if len(self.players) == MAX_PLAYERS:
            return JoinResult.FULL
        self.players[player.user_id] = player
        return JoinResult.JOINED

    def start(self, actor_id: int, is_admin: bool) -> StartResult:
        if actor_id != self.initiator_id and not is_admin:
            return StartResult.UNAUTHORIZED
        if not self.can_start:
            return StartResult.TOO_FEW_PLAYERS
        self.started = True
        return StartResult.STARTED

    def set_mission_count(
        self, actor_id: int, is_admin: bool, mission_count: int
    ) -> MissionCountResult:
        if self.started:
            return MissionCountResult.STARTED
        if actor_id != self.initiator_id and not is_admin:
            return MissionCountResult.UNAUTHORIZED
        if self.variant is not GameVariant.CLASSIC or mission_count not in {3, 5}:
            return MissionCountResult.INVALID
        self.mission_count = mission_count
        return MissionCountResult.UPDATED

    def set_variant(
        self, actor_id: int, is_admin: bool, variant: GameVariant
    ) -> VariantResult:
        if self.started:
            return VariantResult.STARTED
        if actor_id != self.initiator_id and not is_admin:
            return VariantResult.UNAUTHORIZED
        self.variant = variant
        return VariantResult.UPDATED
