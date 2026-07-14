"""aiogram handlers for the Resistance game lifecycle."""

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, User
from aiogram.utils.keyboard import InlineKeyboardBuilder

from resistance.domain import JoinResult, Lobby, MissionCountResult, Player, StartResult
from resistance.game import GamePlayer, Match, MissionResult, Phase, Role, TeamVoteResult
from resistance.game_store import CreateResult, GameStore
from resistance.i18n import DEFAULT_LANGUAGE, Translator
from resistance.settings_store import SettingsStore
from resistance.statistics_store import StatisticsStore


class GameCallback(CallbackData, prefix="res"):
    chat_id: int
    operation: str
    value: str


def create_game_router(
    games: GameStore, settings: SettingsStore, statistics: StatisticsStore
) -> Router:
    router = Router(name="game")

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        translator = _translator(settings, message)
        keyboard = _main_menu_keyboard(translator, message.chat.id) if _is_group(message) else None
        await message.answer(translator.text("start.description"), reply_markup=keyboard)

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(_translator(settings, message).text("help.commands"))

    @router.message(Command("rules"))
    async def rules(message: Message) -> None:
        await message.answer(_translator(settings, message).text("rules.link"))

    @router.message(Command("symbols"))
    async def symbols(message: Message) -> None:
        await message.answer(_translator(settings, message).text("symbols.text"))

    @router.message(Command("ping"))
    async def ping(message: Message) -> None:
        await message.answer(_translator(settings, message).text("ping"))

    @router.message(Command("newgame"))
    async def new_game(message: Message, bot: Bot) -> None:
        if not _is_group(message):
            await message.answer(_translator(settings, message).text("group.only"))
            return
        await _create_lobby(bot, games, settings, message.chat.id, _user(message))

    @router.message(Command("join"))
    async def join(message: Message, bot: Bot) -> None:
        if not _is_group(message):
            await message.answer(_translator(settings, message).text("group.only"))
            return
        await _join_lobby(bot, games, settings, message.chat.id, _user(message))

    @router.message(Command("startgame"))
    async def start_game(message: Message, bot: Bot) -> None:
        if not _is_group(message):
            await message.answer(_translator(settings, message).text("group.only"))
            return
        await _start_lobby(bot, games, settings, message.chat.id, _user(message))

    @router.message(Command("missions"))
    async def missions(message: Message, bot: Bot) -> None:
        if not _is_group(message):
            await message.answer(_translator(settings, message).text("group.only"))
            return
        parts = (message.text or "").split()
        if len(parts) != 2 or parts[1] not in {"3", "5"}:
            await message.answer(_translator(settings, message).text("missions.usage"))
            return
        await _set_lobby_missions(
            bot, games, settings, message.chat.id, _user(message), int(parts[1])
        )

    @router.message(Command("cancelgame"))
    async def cancel_game(message: Message, bot: Bot) -> None:
        if not _is_group(message):
            await message.answer(_translator(settings, message).text("group.only"))
            return
        await _cancel_lobby(bot, games, settings, message.chat.id, _user(message))

    @router.callback_query(GameCallback.filter(F.operation == "lobby_create"))
    async def lobby_create(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        message = _group_callback_message(callback, callback_data)
        if message is None:
            await callback.answer()
            return
        await callback.answer()
        await _create_lobby(bot, games, settings, message.chat.id, callback.from_user)

    @router.callback_query(GameCallback.filter(F.operation == "lobby_join"))
    async def lobby_join(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        message = _group_callback_message(callback, callback_data)
        if message is None:
            await callback.answer()
            return
        await callback.answer()
        await _join_lobby(bot, games, settings, message.chat.id, callback.from_user)

    @router.callback_query(GameCallback.filter(F.operation == "lobby_missions"))
    async def lobby_missions(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        message = _group_callback_message(callback, callback_data)
        if message is None or callback_data.value not in {"3", "5"}:
            await callback.answer()
            return
        await callback.answer()
        result = await _set_lobby_missions(
            bot,
            games,
            settings,
            message.chat.id,
            callback.from_user,
            int(callback_data.value),
        )
        lobby = games.lobby(message.chat.id)
        if result is MissionCountResult.UPDATED and lobby is not None:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=_lobby_keyboard(
                    _group_translator(settings, message.chat.id), lobby
                ),
            )

    @router.callback_query(GameCallback.filter(F.operation == "lobby_start"))
    async def lobby_start(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        message = _group_callback_message(callback, callback_data)
        if message is None:
            await callback.answer()
            return
        await callback.answer()
        await _start_lobby(bot, games, settings, message.chat.id, callback.from_user)

    @router.callback_query(GameCallback.filter(F.operation == "lobby_cancel"))
    async def lobby_cancel(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        message = _group_callback_message(callback, callback_data)
        if message is None:
            await callback.answer()
            return
        await callback.answer()
        await _cancel_lobby(bot, games, settings, message.chat.id, callback.from_user)

    @router.message(Command("board"))
    async def board(message: Message) -> None:
        match = games.match(message.chat.id)
        if match is None:
            await message.answer(_translator(settings, message).text("lobby.missing"))
            return
        await message.answer(_board(_translator(settings, message), match))

    @router.message(Command("votes"))
    async def votes(message: Message) -> None:
        match = games.match(message.chat.id)
        translator = _translator(settings, message)
        voting = _active_voting(match)
        if voting is None:
            await message.answer(translator.text("stats.missing"))
            return
        voters, recorded = voting
        await message.answer(translator.text("stats.votes", count=len(recorded), total=len(voters)))

    @router.message(Command("calltovote"))
    async def call_to_vote(message: Message) -> None:
        match = games.match(message.chat.id)
        translator = _translator(settings, message)
        voting = _active_voting(match)
        if match is None or voting is None:
            await message.answer(translator.text("stats.missing"))
            return
        voters, recorded = voting
        players = ", ".join(
            f'<a href="tg://user?id={user_id}">{match.players[user_id].name}</a>'
            for user_id in voters
            if user_id not in recorded
        )
        await message.answer(translator.text("stats.reminder", players=players), parse_mode="HTML")

    @router.message(Command("stats"))
    async def statistics_command(message: Message) -> None:
        if not _is_group(message):
            await message.answer(_translator(settings, message).text("group.only"))
            return
        player = statistics.player_statistics(message.chat.id, _user(message).id)
        chat = statistics.chat_statistics(message.chat.id)
        await message.answer(
            _group_translator(settings, message.chat.id).text(
                "stats.summary",
                games=player.games,
                wins=player.wins,
                group_games=chat.games,
                villager_wins=chat.villager_wins,
                werewolf_wins=chat.werewolf_wins,
            )
        )

    @router.callback_query(GameCallback.filter(F.operation == "team_toggle"))
    async def team_toggle(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        match = games.match(callback_data.chat_id)
        if match is None:
            await callback.answer()
            return
        try:
            match.toggle_team_member(callback.from_user.id, int(callback_data.value))
        except ValueError:
            await _unavailable(callback, settings, match)
            return
        games.save(match.chat_id)
        await callback.answer()
        message = callback.message
        if isinstance(message, Message):
            await bot.edit_message_reply_markup(
                chat_id=callback.from_user.id,
                message_id=message.message_id,
                reply_markup=_team_keyboard(_user_translator(settings, callback.from_user), match),
            )

    @router.callback_query(GameCallback.filter(F.operation == "team_confirm"))
    async def team_confirm(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        match = games.match(callback_data.chat_id)
        if match is None:
            await callback.answer()
            return
        try:
            match.propose_team(callback.from_user.id)
        except ValueError:
            await _unavailable(callback, settings, match)
            return
        games.save(match.chat_id)
        await callback.answer()
        await _advance(bot, settings, match)

    @router.callback_query(GameCallback.filter(F.operation == "team_vote"))
    async def team_vote(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        match = games.match(callback_data.chat_id)
        if match is None:
            await callback.answer()
            return
        try:
            result = match.vote_team(callback.from_user.id, callback_data.value == "yes")
        except ValueError:
            await _unavailable(callback, settings, match)
            return
        games.save(match.chat_id)
        await callback.answer()
        if result is TeamVoteResult.PENDING:
            return
        await bot.send_message(match.chat_id, _team_vote_summary(settings, match, result))
        if match.phase is Phase.FINISHED:
            await _finish(bot, settings, games, statistics, match)
        else:
            await _advance(bot, settings, match)

    @router.callback_query(GameCallback.filter(F.operation == "mission_vote"))
    async def mission_vote(
        callback: CallbackQuery, callback_data: GameCallback, bot: Bot
    ) -> None:
        match = games.match(callback_data.chat_id)
        if match is None:
            await callback.answer()
            return
        try:
            result = match.vote_mission(callback.from_user.id, callback_data.value == "success")
        except ValueError:
            await _unavailable(callback, settings, match)
            return
        games.save(match.chat_id)
        await callback.answer()
        if result is MissionResult.PENDING:
            return
        translator = _group_translator(settings, match.chat_id)
        key = "mission.result.success" if result is MissionResult.SUCCESS else "mission.result.failed"
        await bot.send_message(
            match.chat_id, translator.text(key, sabotages=match.last_sabotages)
        )
        if match.phase is Phase.FINISHED:
            await _finish(bot, settings, games, statistics, match)
        else:
            await _advance(bot, settings, match)

    return router


async def _create_lobby(
    bot: Bot, games: GameStore, settings: SettingsStore, chat_id: int, user: User
) -> None:
    result = games.create_lobby(chat_id, user.id)
    translator = _group_translator(settings, chat_id)
    lobby = games.lobby(chat_id)
    keyboard = _lobby_keyboard(translator, lobby) if lobby is not None else None
    key = "lobby.created" if result is CreateResult.CREATED else "lobby.exists"
    await bot.send_message(chat_id, translator.text(key), reply_markup=keyboard)


async def _join_lobby(
    bot: Bot, games: GameStore, settings: SettingsStore, chat_id: int, user: User
) -> None:
    translator = _group_translator(settings, chat_id)
    if games.lobby(chat_id) is not None:
        try:
            await bot.send_message(user.id, _user_translator(settings, user).text("start.description"))
        except TelegramForbiddenError:
            await bot.send_message(chat_id, translator.text("join.private_chat"))
            return
    result = games.join(chat_id, Player(user.id, user.full_name))
    keys = {
        JoinResult.JOINED: "lobby.joined",
        JoinResult.ALREADY_JOINED: "lobby.already_joined",
        JoinResult.FULL: "lobby.full",
        JoinResult.STARTED: "lobby.started",
        JoinResult.MISSING: "lobby.missing",
    }
    values = {"name": user.full_name} if result is JoinResult.JOINED else {}
    await bot.send_message(chat_id, translator.text(keys[result], **values))


async def _start_lobby(
    bot: Bot, games: GameStore, settings: SettingsStore, chat_id: int, user: User
) -> None:
    result = games.start(chat_id, user.id, await _is_group_admin(bot, chat_id, user.id))
    translator = _group_translator(settings, chat_id)
    key = {
        StartResult.MISSING: "lobby.missing",
        StartResult.UNAUTHORIZED: "lobby.start_forbidden",
        StartResult.TOO_FEW_PLAYERS: "lobby.need_players",
    }.get(result)
    if key is not None:
        await bot.send_message(chat_id, translator.text(key))
        return
    match = games.match(chat_id)
    assert match is not None
    await bot.send_message(chat_id, translator.text("game.started", players=len(match.players)))
    await _inform_roles(bot, settings, match)
    await _advance(bot, settings, match)


async def _set_lobby_missions(
    bot: Bot,
    games: GameStore,
    settings: SettingsStore,
    chat_id: int,
    user: User,
    mission_count: int,
) -> MissionCountResult:
    result = games.set_mission_count(
        chat_id,
        user.id,
        await _is_group_admin(bot, chat_id, user.id),
        mission_count,
    )
    key = {
        MissionCountResult.UPDATED: "missions.updated",
        MissionCountResult.UNAUTHORIZED: "lobby.start_forbidden",
        MissionCountResult.INVALID: "missions.usage",
        MissionCountResult.STARTED: "lobby.started",
        MissionCountResult.MISSING: "lobby.missing",
    }[result]
    await bot.send_message(
        chat_id, _group_translator(settings, chat_id).text(key, count=mission_count)
    )
    return result


async def _cancel_lobby(
    bot: Bot, games: GameStore, settings: SettingsStore, chat_id: int, user: User
) -> None:
    lobby = games.lobby(chat_id)
    match = games.match(chat_id)
    initiator_id = lobby.initiator_id if lobby is not None else None
    if initiator_id is None and match is not None:
        initiator_id = match.initiator_id
    translator = _group_translator(settings, chat_id)
    if initiator_id is None:
        await bot.send_message(chat_id, translator.text("lobby.missing"))
        return
    if user.id != initiator_id and not await _is_group_admin(bot, chat_id, user.id):
        await bot.send_message(chat_id, translator.text("lobby.start_forbidden"))
        return
    games.cancel(chat_id)
    await bot.send_message(chat_id, translator.text("game.cancelled"))


async def _advance(bot: Bot, settings: SettingsStore, match: Match) -> None:
    group_translator = _group_translator(settings, match.chat_id)
    if match.phase is Phase.BUILD_TEAM:
        leader = match.players[match.leader_id]
        await bot.send_message(
            match.chat_id,
            group_translator.text(
                "round.build",
                mission=match.mission_index + 1,
                total=match.mission_count,
                leader=leader.name,
                size=match.required_team_size,
            ),
        )
        translator = _player_translator(settings, leader)
        await bot.send_message(
            leader.user_id,
            translator.text("team.choose", size=match.required_team_size),
            reply_markup=_team_keyboard(translator, match),
        )
    elif match.phase is Phase.TEAM_VOTE:
        assert match.proposed_team is not None
        members = _names(match, match.proposed_team)
        await bot.send_message(
            match.chat_id,
            group_translator.text(
                "team.proposed", leader=match.players[match.leader_id].name, members=members
            ),
        )
        for player in match.players.values():
            translator = _player_translator(settings, player)
            await bot.send_message(
                player.user_id,
                translator.text("team.vote.prompt", members=members),
                reply_markup=_team_vote_keyboard(translator, match),
            )
    elif match.phase is Phase.MISSION:
        assert match.proposed_team is not None
        await bot.send_message(
            match.chat_id,
            group_translator.text("mission.departed", members=_names(match, match.proposed_team)),
        )
        for user_id in match.proposed_team:
            player = match.players[user_id]
            translator = _player_translator(settings, player)
            await bot.send_message(
                user_id,
                translator.text("mission.prompt"),
                reply_markup=_mission_keyboard(translator, match, player),
            )


def _main_menu_keyboard(translator: Translator, chat_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=translator.text("menu.create"),
        callback_data=GameCallback(chat_id=chat_id, operation="lobby_create", value="go"),
    )
    return builder.as_markup()


def _lobby_keyboard(translator: Translator, lobby: Lobby) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=translator.text("menu.join"),
        callback_data=GameCallback(
            chat_id=lobby.chat_id, operation="lobby_join", value="go"
        ),
    )
    for mission_count in (3, 5):
        selected = "✓ " if lobby.mission_count == mission_count else ""
        builder.button(
            text=f"{selected}{translator.text(f'menu.missions.{mission_count}')}",
            callback_data=GameCallback(
                chat_id=lobby.chat_id,
                operation="lobby_missions",
                value=str(mission_count),
            ),
        )
    builder.button(
        text=translator.text("menu.start"),
        callback_data=GameCallback(
            chat_id=lobby.chat_id, operation="lobby_start", value="go"
        ),
    )
    builder.button(
        text=translator.text("menu.cancel"),
        callback_data=GameCallback(
            chat_id=lobby.chat_id, operation="lobby_cancel", value="go"
        ),
    )
    builder.adjust(1, 2, 2)
    return builder.as_markup()


def _team_keyboard(translator: Translator, match: Match) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user_id in match.turn_order:
        prefix = "✓ " if user_id in match.selected_team else ""
        builder.button(
            text=f"{prefix}{match.players[user_id].name}",
            callback_data=GameCallback(
                chat_id=match.chat_id, operation="team_toggle", value=str(user_id)
            ),
        )
    if len(match.selected_team) == match.required_team_size:
        builder.button(
            text=translator.text("team.confirm"),
            callback_data=GameCallback(
                chat_id=match.chat_id, operation="team_confirm", value="go"
            ),
        )
    builder.adjust(1)
    return builder.as_markup()


def _team_vote_keyboard(translator: Translator, match: Match) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=translator.text("team.vote.yes"),
        callback_data=GameCallback(chat_id=match.chat_id, operation="team_vote", value="yes"),
    )
    builder.button(
        text=translator.text("team.vote.no"),
        callback_data=GameCallback(chat_id=match.chat_id, operation="team_vote", value="no"),
    )
    builder.adjust(2)
    return builder.as_markup()


def _mission_keyboard(
    translator: Translator, match: Match, player: GamePlayer
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=translator.text("mission.success"),
        callback_data=GameCallback(
            chat_id=match.chat_id, operation="mission_vote", value="success"
        ),
    )
    if player.role is Role.WEREWOLF:
        builder.button(
            text=translator.text("mission.sabotage"),
            callback_data=GameCallback(
                chat_id=match.chat_id, operation="mission_vote", value="sabotage"
            ),
        )
    builder.adjust(1)
    return builder.as_markup()


async def _inform_roles(bot: Bot, settings: SettingsStore, match: Match) -> None:
    werewolves = [player for player in match.players.values() if player.role is Role.WEREWOLF]
    for player in match.players.values():
        translator = _player_translator(settings, player)
        await bot.send_message(
            player.user_id, translator.text("game.role", role=_label(translator, player.role))
        )
        if player.role is Role.WEREWOLF:
            await bot.send_message(
                player.user_id,
                translator.text(
                    "game.werewolves", names=", ".join(werewolf.name for werewolf in werewolves)
                ),
            )


async def _finish(
    bot: Bot,
    settings: SettingsStore,
    games: GameStore,
    statistics: StatisticsStore,
    match: Match,
) -> None:
    statistics.record(match)
    translator = _group_translator(settings, match.chat_id)
    assert match.winner is not None
    roles = "\n".join(
        translator.text("roles", name=player.name, role=_label(translator, player.role))
        for player in match.players.values()
    )
    await bot.send_message(
        match.chat_id,
        translator.text("game.over", winner=_label(translator, match.winner), roles=roles),
    )
    games.cancel(match.chat_id)


def _team_vote_summary(
    settings: SettingsStore, match: Match, result: TeamVoteResult
) -> str:
    assert match.team_votes is not None
    translator = _group_translator(settings, match.chat_id)
    approved = _names(match, [user_id for user_id, vote in match.team_votes.items() if vote]) or "—"
    rejected = _names(match, [user_id for user_id, vote in match.team_votes.items() if not vote]) or "—"
    key = "team.vote.approved" if result is TeamVoteResult.APPROVED else "team.vote.rejected"
    return translator.text(
        key, approved=approved, rejected=rejected, attempts=match.rejected_teams
    )


def _board(translator: Translator, match: Match) -> str:
    markers = {
        MissionResult.SUCCESS: "✅",
        MissionResult.FAILED: "❌",
    }
    missions = " ".join(
        [markers[result] for result in match.mission_results]
        + ["⬜"] * (match.mission_count - len(match.mission_results))
    )
    return translator.text(
        "board",
        missions=missions,
        successes=match.successful_missions,
        failures=match.failed_missions,
        wins=match.wins_required,
        rejected=match.rejected_teams,
        mission=match.mission_index + 1,
        total=match.mission_count,
        size=match.required_team_size,
        order=" → ".join(match.players[user_id].name for user_id in match.turn_order),
    )


def _active_voting(match: Match | None) -> tuple[list[int], dict[int, bool]] | None:
    if match is None:
        return None
    if match.phase is Phase.TEAM_VOTE and match.team_votes is not None:
        return match.turn_order, match.team_votes
    if (
        match.phase is Phase.MISSION
        and match.proposed_team is not None
        and match.mission_votes is not None
    ):
        return match.proposed_team, match.mission_votes
    return None


def _group_callback_message(
    callback: CallbackQuery, callback_data: GameCallback
) -> Message | None:
    message = callback.message
    if (
        not isinstance(message, Message)
        or not _is_group(message)
        or message.chat.id != callback_data.chat_id
    ):
        return None
    return message


async def _unavailable(callback: CallbackQuery, settings: SettingsStore, match: Match) -> None:
    await callback.answer(
        _group_translator(settings, match.chat_id).text("error.unavailable"), show_alert=True
    )


def _names(match: Match, user_ids: list[int]) -> str:
    return ", ".join(match.players[user_id].name for user_id in user_ids)


def _is_group(message: Message) -> bool:
    return message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}


def _user(message: Message) -> User:
    assert message.from_user is not None
    return message.from_user


def _translator(settings: SettingsStore, message: Message) -> Translator:
    if _is_group(message):
        return _group_translator(settings, message.chat.id)
    return _user_translator(settings, _user(message))


def _group_translator(settings: SettingsStore, chat_id: int) -> Translator:
    return Translator(settings.chat_language(chat_id) or DEFAULT_LANGUAGE)


def _user_translator(settings: SettingsStore, user: User) -> Translator:
    return Translator(settings.user_language(user.id) or user.language_code or DEFAULT_LANGUAGE)


def _player_translator(settings: SettingsStore, player: GamePlayer) -> Translator:
    return Translator(settings.user_language(player.user_id) or DEFAULT_LANGUAGE)


def _label(translator: Translator, role: Role) -> str:
    return translator.text(f"label.{role.value}")


async def _is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
