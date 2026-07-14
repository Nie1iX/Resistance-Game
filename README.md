# Resistance Telegram Bot

A Telegram bot for playing a social deduction game without a dedicated moderator.

## Features

- Supports groups of 5 to 10 players.
- Delivers secret roles and actions through private chats.
- Publishes team proposals, open votes, and mission results in the group.
- Offers short three-mission and standard five-mission games.
- Restores active lobbies and matches from SQLite after a restart.
- Tracks completed games in group statistics.
- Includes English and Russian translations.

## How to Play

1. Add the bot to a group and open a private chat with it.
2. Run `/newgame` in the group.
3. Each player joins with `/join`.
4. The lobby creator or a group administrator selects `/missions 3` or `/missions 5`.
5. The lobby creator or a group administrator starts the game with `/startgame`.
6. Follow private prompts for secret actions and group messages for public decisions.

The game uses strict-majority team voting. Five rejected teams in one round give the hidden side an immediate victory. In a five-mission game with at least seven players, the fourth mission requires two sabotage votes to fail.

## Commands

- `/start`, `/help`, `/rules`, `/symbols`, `/ping` — bot information and help.
- `/newgame`, `/join`, `/missions 3|5`, `/startgame`, `/cancelgame` — lobby management.
- `/board`, `/votes`, `/calltovote` — current game state and voting controls.
- `/stats` — group statistics.
- `/language`, `/grouplanguage` — private and group language settings.

## Quick Start

```bash
uv sync --group dev
export BOT_TOKEN=123456:token
export DATABASE_PATH=resistance.db
uv run python -m resistance.app
```

## Configuration

| Variable | Description | Default |
| --- | --- | --- |
| `BOT_TOKEN` | Telegram bot token | Required |
| `DATABASE_PATH` | SQLite database path | `resistance.db` |

## Development

```bash
uv run --group dev pybabel compile --directory resistance/locales --domain messages
uv run --group dev pytest -q
uv run --group dev ruff check .
uv run --group dev mypy resistance
```

## Docker Compose

```bash
cp .env.example .env
# Set BOT_TOKEN in .env.
docker compose up --build -d
```

SQLite data is stored in the `resistance-data` volume at `/data/resistance.db`. Running `docker compose down` preserves the data; add `--volumes` only when the stored state should be deleted.
