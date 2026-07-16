import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import admin as admin_handlers
import contact as contact_handlers
import questions_admin as questions_admin_handlers
import quiz as quiz_handlers
import start as start_handlers
import status as status_handlers
from admin_middleware import AdminOnlyMiddleware
from config import settings
from db_middleware import DatabaseMiddleware
from logging_config import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("Bot ishga tushmoqda...")

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())

    # Global middleware: har bir update uchun DB session
    dispatcher.update.middleware(DatabaseMiddleware())

    # Faqat admin router uchun cheklov middleware
    admin_handlers.router.message.middleware(AdminOnlyMiddleware())
    admin_handlers.router.callback_query.middleware(AdminOnlyMiddleware())
    questions_admin_handlers.router.message.middleware(AdminOnlyMiddleware())
    questions_admin_handlers.router.callback_query.middleware(AdminOnlyMiddleware())

    # Routerlarni ketma-ket ulaymiz (admin birinchi bo'lishi shart emas,
    # chunki komandalar/callbacklar bir-biriga to'qnashmaydi)
    dispatcher.include_router(start_handlers.router)
    dispatcher.include_router(status_handlers.router)
    dispatcher.include_router(quiz_handlers.router)
    dispatcher.include_router(contact_handlers.router)
    dispatcher.include_router(admin_handlers.router)
    dispatcher.include_router(questions_admin_handlers.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Polling boshlandi.")
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot to'xtatildi.")