"""In-memory ownership of lobbies and active matches."""

from dataclasses import dataclass, field
from enum import Enum, auto
from random import Random

from resistance.domain import (
    GameVariant,
    JoinResult,
    Lobby,
    MissionCountResult,
    Player,
    StartResult,
    VariantResult,
)
from resistance.game import Match
from resistance.game_persistence import GamePersistence


class CreateResult(Enum):
    CREATED = auto()
    EXISTS = auto()


@dataclass
class GameStore:
    random: Random
    persistence: GamePersistence | None = None
    _lobbies: dict[int, Lobby] = field(default_factory=dict)
    _matches: dict[int, Match] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.persistence is not None:
            self._lobbies, self._matches = self.persistence.load()

    def lobby(self, chat_id: int) -> Lobby | None:
        return self._lobbies.get(chat_id)

    def match(self, chat_id: int) -> Match | None:
        return self._matches.get(chat_id)

    def create_lobby(self, chat_id: int, initiator_id: int) -> CreateResult:
        if chat_id in self._lobbies or chat_id in self._matches:
            return CreateResult.EXISTS
        self._lobbies[chat_id] = Lobby(chat_id, initiator_id)
        self._save_lobby(chat_id)
        return CreateResult.CREATED

    def join(self, chat_id: int, player: Player) -> JoinResult:
        lobby = self.lobby(chat_id)
        if lobby is None:
            return JoinResult.MISSING
        result = lobby.join(player)
        if result is JoinResult.JOINED:
            self._save_lobby(chat_id)
        return result

    def start(self, chat_id: int, actor_id: int, is_admin: bool) -> StartResult:
        lobby = self.lobby(chat_id)
        if lobby is None:
            return StartResult.MISSING
        result = lobby.start(actor_id, is_admin)
        if result is StartResult.STARTED:
            self._matches[chat_id] = Match.from_lobby(lobby, self.random)
            del self._lobbies[chat_id]
            self._save_match(chat_id)
        return result

    def set_mission_count(
        self, chat_id: int, actor_id: int, is_admin: bool, mission_count: int
    ) -> MissionCountResult:
        lobby = self.lobby(chat_id)
        if lobby is None:
            return (
                MissionCountResult.STARTED
                if self.match(chat_id) is not None
                else MissionCountResult.MISSING
            )
        result = lobby.set_mission_count(actor_id, is_admin, mission_count)
        if result is MissionCountResult.UPDATED:
            self._save_lobby(chat_id)
        return result

    def set_variant(
        self,
        chat_id: int,
        actor_id: int,
        is_admin: bool,
        variant: GameVariant,
    ) -> VariantResult:
        lobby = self.lobby(chat_id)
        if lobby is None:
            return (
                VariantResult.STARTED
                if self.match(chat_id) is not None
                else VariantResult.MISSING
            )
        result = lobby.set_variant(actor_id, is_admin, variant)
        if result is VariantResult.UPDATED:
            self._save_lobby(chat_id)
        return result

    def cancel(self, chat_id: int) -> bool:
        removed = self._lobbies.pop(chat_id, None) is not None
        removed = self._matches.pop(chat_id, None) is not None or removed
        if removed and self.persistence is not None:
            self.persistence.delete(chat_id)
        return removed

    def save(self, chat_id: int) -> None:
        if chat_id in self._lobbies:
            self._save_lobby(chat_id)
        elif chat_id in self._matches:
            self._save_match(chat_id)

    def _save_lobby(self, chat_id: int) -> None:
        if self.persistence is not None:
            self.persistence.save_lobby(self._lobbies[chat_id])

    def _save_match(self, chat_id: int) -> None:
        if self.persistence is not None:
            self.persistence.save_match(self._matches[chat_id])
