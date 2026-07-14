"""Application entry point."""

import asyncio
from random import Random

from aiogram import Bot, Dispatcher

from resistance.config import Settings, load_settings
from resistance.game_handlers import create_game_router
from resistance.game_persistence import GamePersistence
from resistance.game_store import GameStore
from resistance.handlers import create_router
from resistance.i18n import I18N, LocaleMiddleware
from resistance.settings_store import SettingsStore
from resistance.statistics_store import StatisticsStore


def create_dispatcher(store: SettingsStore) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(store))
    dispatcher.include_router(
        create_game_router(
            GameStore(Random(), GamePersistence(store.database_path)),
            store,
            StatisticsStore(store.database_path),
        )
    )
    LocaleMiddleware(I18N, store).setup(dispatcher)
    return dispatcher


async def run(settings: Settings) -> None:
    bot = Bot(settings.bot_token)
    try:
        await create_dispatcher(SettingsStore(settings.database_path)).start_polling(bot)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(run(load_settings()))


if __name__ == "__main__":
    main()
