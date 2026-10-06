from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import config
from database import db


class AdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return config.is_admin(event.from_user.id if event.from_user else None)


class PrivateChatMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = None
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery) and event.message:
            chat = event.message.chat
        chat_type = getattr(chat.type, "value", chat.type) if chat is not None else None
        if chat is not None and chat_type != "private":
            if isinstance(event, Message):
                await event.answer("Для защиты данных заказы и админ-панель работают только в личном чате с ботом.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Откройте личный чат с ботом.", show_alert=True)
            return None
        return await handler(event, data)


class UserRegistryMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        chat = None
        if isinstance(event, Message):
            chat = event.chat
        elif isinstance(event, CallbackQuery) and event.message:
            chat = event.message.chat
        chat_type = getattr(chat.type, "value", chat.type) if chat is not None else None
        if user and chat_type == "private":
            db.ensure_user(user.id)
        return await handler(event, data)


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user and db.is_banned(user.id):
            if isinstance(event, Message):
                await event.answer("Ваш аккаунт заблокирован администратором :)")
            elif isinstance(event, CallbackQuery):
                await event.answer("Ваш аккаунт заблокирован :)", show_alert=True)
            return None
        return await handler(event, data)
