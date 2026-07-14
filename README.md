# Resistance Telegram Bot

A Telegram bot for playing social deduction games without a dedicated moderator.

## Features

- Supports groups of 5 to 10 players.
- Offers Classic and Werewolves rulesets.
- Delivers secret roles and actions through private chats.
- Publishes team proposals, open votes, and mission results in the group.
- Uses an InlineKeyboard lobby for ruleset, game length, start, and cancel actions.
- Restores active lobbies and matches from SQLite after a restart.
- Tracks completed games in group statistics.
- Includes English and Russian translations.

## Game Variants

### Classic

Classic follows the standard Resistance mission structure:

- Choose a short three-mission game or a standard five-mission game.
- Win two of three missions or three of five missions.
- Use the standard role distribution and mission team sizes.
- Require a strict majority to approve a proposed team.
- Give the hidden side an immediate victory after five rejected teams in one mission.
- Require two sabotage votes to fail the fourth mission with 7–10 players.

### Werewolves

Werewolves follows the original village-themed rules:

- The village starts with three curses and three health.
- A successful patrol removes one curse; a failed patrol removes one village health.
- The first side to remove all three opposing markers wins.
- Patrols start with two players in groups of 5–7 and three players in groups of 8–10.
- Each successful patrol increases the next patrol size by one, capped at three players in a five-player game.
- One attack is enough to fail a patrol.
- Rejected team proposals rotate the leader without an automatic loss after five rejections.

## How to Play

1. Add the bot to a group, open a private chat with it, and run `/start` in the group.
2. Create a game and let each player join from the lobby panel.
3. Select Classic or Werewolves. For Classic, also select three or five missions.
4. The lobby creator or a group administrator starts the game from the same panel.
5. Follow private prompts for secret actions and group messages for public decisions.

## Commands

- `/start`, `/help`, `/rules`, `/symbols`, `/ping` — bot information and help.
- `/newgame`, `/join`, `/missions 3|5`, `/startgame`, `/cancelgame` — command fallback for lobby actions.
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
