"""SQLite snapshots for active lobbies and matches."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resistance.domain import Lobby, Player
from resistance.game import GamePlayer, Match, MissionResult, Phase, Role


@dataclass(frozen=True)
class GamePersistence:
    database_path: Path

    def __post_init__(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS active_games "
                "(chat_id INTEGER PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL)"
            )

    def load(self) -> tuple[dict[int, Lobby], dict[int, Match]]:
        lobbies: dict[int, Lobby] = {}
        matches: dict[int, Match] = {}
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute("SELECT chat_id, kind, state FROM active_games").fetchall()
        for chat_id, kind, encoded_state in rows:
            state = json.loads(str(encoded_state))
            if kind == "lobby":
                lobbies[int(chat_id)] = _lobby_from_state(state)
            elif kind == "match":
                matches[int(chat_id)] = _match_from_state(state)
            else:
                raise ValueError(f"Unknown active game kind: {kind}")
        return lobbies, matches

    def save_lobby(self, lobby: Lobby) -> None:
        self._save(lobby.chat_id, "lobby", _lobby_to_state(lobby))

    def save_match(self, match: Match) -> None:
        self._save(match.chat_id, "match", _match_to_state(match))

    def delete(self, chat_id: int) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("DELETE FROM active_games WHERE chat_id = ?", (chat_id,))

    def _save(self, chat_id: int, kind: str, state: dict[str, Any]) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "INSERT INTO active_games(chat_id, kind, state) VALUES (?, ?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET kind = excluded.kind, state = excluded.state",
                (chat_id, kind, json.dumps(state, separators=(",", ":"))),
            )


def _lobby_to_state(lobby: Lobby) -> dict[str, Any]:
    return {
        "chat_id": lobby.chat_id,
        "initiator_id": lobby.initiator_id,
        "mission_count": lobby.mission_count,
        "players": [{"user_id": player.user_id, "name": player.name} for player in lobby.players.values()],
        "started": lobby.started,
    }


def _lobby_from_state(state: dict[str, Any]) -> Lobby:
    players = {
        int(player["user_id"]): Player(int(player["user_id"]), str(player["name"]))
        for player in state["players"]
    }
    return Lobby(
        chat_id=int(state["chat_id"]),
        initiator_id=int(state["initiator_id"]),
        mission_count=int(state.get("mission_count", 5)),
        players=players,
        started=bool(state["started"]),
    )


def _match_to_state(match: Match) -> dict[str, Any]:
    return {
        "match_id": match.match_id,
        "chat_id": match.chat_id,
        "initiator_id": match.initiator_id,
        "players": [
            {"user_id": player.user_id, "name": player.name, "role": player.role.value}
            for player in match.players.values()
        ],
        "turn_order": match.turn_order,
        "phase": match.phase.name,
        "mission_count": match.mission_count,
        "leader_index": match.leader_index,
        "mission_index": match.mission_index,
        "successful_missions": match.successful_missions,
        "failed_missions": match.failed_missions,
        "rejected_teams": match.rejected_teams,
        "selected_team": match.selected_team,
        "proposed_team": match.proposed_team,
        "team_votes": match.team_votes,
        "mission_votes": match.mission_votes,
        "mission_results": [result.value for result in match.mission_results],
        "last_sabotages": match.last_sabotages,
        "winner": None if match.winner is None else match.winner.value,
    }


def _match_from_state(state: dict[str, Any]) -> Match:
    players = {
        int(player["user_id"]): GamePlayer(
            int(player["user_id"]), str(player["name"]), Role(str(player["role"]))
        )
        for player in state["players"]
    }
    return Match(
        chat_id=int(state["chat_id"]),
        initiator_id=int(state["initiator_id"]),
        players=players,
        turn_order=[int(user_id) for user_id in state["turn_order"]],
        phase=Phase[str(state["phase"])],
        mission_count=int(state.get("mission_count", 5)),
        match_id=str(state["match_id"]),
        leader_index=int(state["leader_index"]),
        mission_index=int(state["mission_index"]),
        successful_missions=int(state["successful_missions"]),
        failed_missions=int(state["failed_missions"]),
        rejected_teams=int(state["rejected_teams"]),
        selected_team=[int(user_id) for user_id in state["selected_team"]],
        proposed_team=_optional_ids(state["proposed_team"]),
        team_votes=_optional_votes(state["team_votes"]),
        mission_votes=_optional_votes(state["mission_votes"]),
        mission_results=[MissionResult(str(result)) for result in state["mission_results"]],
        last_sabotages=int(state["last_sabotages"]),
        winner=None if state["winner"] is None else Role(str(state["winner"])),
    )


def _optional_ids(values: Any) -> list[int] | None:
    return None if values is None else [int(value) for value in values]


def _optional_votes(values: Any) -> dict[int, bool] | None:
    return None if values is None else {int(user_id): bool(value) for user_id, value in values.items()}
