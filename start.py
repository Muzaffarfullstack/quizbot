import logging
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards import start_test_keyboard
from service import QuizService

logger = logging.getLogger(__name__)
router = Router(name="start")

WELCOME_TEXT = (
    "Assalomu alaykum.\n"
    "Shifokorlar bilim testiga xush kelibsiz.\n\n"
    "Testni boshlash uchun tugmani bosing."
)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    service = QuizService(session)
    await service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    await message.answer(WELCOME_TEXT, reply_markup=start_test_keyboard())
    logger.info("start_test ko'rsatildi: telegram_id=%s", message.from_user.id)