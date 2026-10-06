import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from handlers import admin, calculator, common, order
from middleware import BanMiddleware, PrivateChatMiddleware, UserRegistryMiddleware


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        stream=sys.stdout,
    )
    config.validate()
    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(PrivateChatMiddleware())
    dp.callback_query.outer_middleware(PrivateChatMiddleware())
    dp.message.outer_middleware(UserRegistryMiddleware())
    dp.callback_query.outer_middleware(UserRegistryMiddleware())
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())
    dp.include_router(common.router)
    dp.include_router(calculator.router)
    dp.include_router(order.router)
    dp.include_router(admin.router)
    logging.getLogger(__name__).info("Бот запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
