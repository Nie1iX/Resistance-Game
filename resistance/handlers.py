"""aiogram handlers for language selection."""

from aiogram import Bot, F, Router
from aiogram.enums import ChatMemberStatus, ChatType
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from resistance.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, Translator
from resistance.settings_store import SettingsStore


LANGUAGE_LABELS = {"en": "English", "ru": "Русский"}


class LanguageSelection(CallbackData, prefix="lang"):
    scope: str
    language: str


def language_keyboard(scope: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for language, label in LANGUAGE_LABELS.items():
        builder.button(text=label, callback_data=LanguageSelection(scope=scope, language=language))
    builder.adjust(2)
    return builder.as_markup()


def create_router(store: SettingsStore) -> Router:
    router = Router(name="language")

    @router.message(Command("language"), F.chat.type == ChatType.PRIVATE)
    async def choose_user_language(message: Message) -> None:
        user = message.from_user
        if user is None:
            return
        language = store.user_language(user.id) or user.language_code or DEFAULT_LANGUAGE
        await message.answer(
            Translator(language).text("language.choose"), reply_markup=language_keyboard("user")
        )

    @router.callback_query(LanguageSelection.filter(F.scope == "user"))
    async def set_user_language(
        callback: CallbackQuery, callback_data: LanguageSelection, bot: Bot
    ) -> None:
        if callback_data.language not in SUPPORTED_LANGUAGES:
            await callback.answer()
            return
        store.set_user_language(callback.from_user.id, callback_data.language)
        translator = Translator(callback_data.language)
        await callback.answer()
        await bot.send_message(
            callback.from_user.id,
            translator.text("language.saved", language=LANGUAGE_LABELS[callback_data.language]),
        )

    @router.message(Command("grouplanguage"))
    async def choose_group_language(message: Message, bot: Bot) -> None:
        user = message.from_user
        if user is None or message.chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            return
        translator = Translator(store.chat_language(message.chat.id) or user.language_code or DEFAULT_LANGUAGE)
        if not await _is_group_admin(bot, message.chat.id, user.id):
            await message.answer(translator.text("language.admin_only"))
            return
        await message.answer(translator.text("language.choose"), reply_markup=language_keyboard("chat"))

    @router.callback_query(LanguageSelection.filter(F.scope == "chat"))
    async def set_group_language(
        callback: CallbackQuery, callback_data: LanguageSelection, bot: Bot
    ) -> None:
        message = callback.message
        if callback_data.language not in SUPPORTED_LANGUAGES or not isinstance(message, Message):
            await callback.answer()
            return
        translator = Translator(store.chat_language(message.chat.id) or DEFAULT_LANGUAGE)
        if not await _is_group_admin(bot, message.chat.id, callback.from_user.id):
            await callback.answer(translator.text("language.admin_only"), show_alert=True)
            return
        store.set_chat_language(message.chat.id, callback_data.language)
        translator = Translator(callback_data.language)
        await callback.answer()
        await bot.send_message(
            message.chat.id,
            translator.text("language.group_saved", language=LANGUAGE_LABELS[callback_data.language]),
        )

    return router


async def _is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
