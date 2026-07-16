import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat

import admin as admin_handlers
import contact as contact_handlers
import questions_admin as questions_admin_handlers
import quiz as quiz_handlers
import start as start_handlers
import status as status_handlers
from admin_middleware import AdminOnlyMiddleware
from config import settings
from database import engine
from db_middleware import DatabaseMiddleware
from logging_config import setup_logging
from model import Base

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("Bot ishga tushmoqda...")

    # alembic/versions bo'sh bo'lgani uchun jadvallarni shu yerda o'zi yaratamiz
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Baza jadvallari tayyor.")

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

    # Telegramning "/" menyu tugmasida hammaga ko'rinadigan komandalar
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Testni boshlash"),
            BotCommand(command="status", description="Natijam va holatim"),
        ]
    )

    # Faqat adminlarga ko'rinadigan qo'shimcha komandalar (ADMIN_IDS dan)
    admin_commands = [
        BotCommand(command="start", description="Testni boshlash"),
        BotCommand(command="status", description="Natijam va holatim"),
        BotCommand(command="winners", description="Tekshiruv kutayotgan g'oliblar"),
        BotCommand(command="redeem", description="Kodni tasdiqlash: /redeem <kod>"),
        BotCommand(command="addquestion", description="Yangi savol qo'shish"),
        BotCommand(command="questions", description="Savollar ro'yxati"),
        BotCommand(command="delquestion", description="Savolni o'chirish"),
        BotCommand(command="togglequestion", description="Savolni yoqish/o'chirish"),
    ]
    for admin_id in settings.admin_ids_list:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:
            logger.exception("Admin uchun komandalarni o'rnatib bo'lmadi: admin_id=%s", admin_id)

    logger.info("Polling boshlandi.")
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot to'xtatildi.")