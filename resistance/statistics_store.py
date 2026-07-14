"""Persistent completed-game statistics."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from resistance.game import Match, Phase


@dataclass(frozen=True)
class PlayerStatistics:
    games: int
    wins: int


@dataclass(frozen=True)
class ChatStatistics:
    games: int
    villager_wins: int
    werewolf_wins: int


@dataclass(frozen=True)
class StatisticsStore:
    database_path: Path

    def __post_init__(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS completed_matches ("
                "match_id TEXT PRIMARY KEY, chat_id INTEGER NOT NULL, winner TEXT NOT NULL, completed_at TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS completed_match_players ("
                "match_id TEXT NOT NULL, user_id INTEGER NOT NULL, role TEXT NOT NULL, "
                "PRIMARY KEY(match_id, user_id))"
            )

    def record(self, match: Match) -> bool:
        if match.phase is not Phase.FINISHED or match.winner is None:
            raise ValueError("Only finished matches can be recorded")
        with sqlite3.connect(self.database_path) as connection:
            result = connection.execute(
                "INSERT OR IGNORE INTO completed_matches(match_id, chat_id, winner, completed_at) "
                "VALUES (?, ?, ?, ?)",
                (match.match_id, match.chat_id, match.winner.value, datetime.now(UTC).isoformat()),
            )
            if result.rowcount == 0:
                return False
            connection.executemany(
                "INSERT INTO completed_match_players(match_id, user_id, role) VALUES (?, ?, ?)",
                [(match.match_id, player.user_id, player.role.value) for player in match.players.values()],
            )
        return True

    def player_statistics(self, chat_id: int, user_id: int) -> PlayerStatistics:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(player.role = match.winner), 0) "
                "FROM completed_match_players AS player "
                "JOIN completed_matches AS match ON match.match_id = player.match_id "
                "WHERE match.chat_id = ? AND player.user_id = ?",
                (chat_id, user_id),
            ).fetchone()
        assert row is not None
        return PlayerStatistics(games=int(row[0]), wins=int(row[1]))

    def chat_statistics(self, chat_id: int) -> ChatStatistics:
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*), COALESCE(SUM(winner = 'villager'), 0), "
                "COALESCE(SUM(winner = 'werewolf'), 0) FROM completed_matches WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        assert row is not None
        return ChatStatistics(games=int(row[0]), villager_wins=int(row[1]), werewolf_wins=int(row[2]))
