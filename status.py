import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model import User, UserStatus, Winner

logger = logging.getLogger(__name__)
router = Router(name="status")


@router.message(Command("status"))
async def cmd_status(message: Message, session: AsyncSession) -> None:
    result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
    user = result.scalar_one_or_none()

    if user is None:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. Boshlash uchun /start bosing.")
        return

    if not user.has_completed_test:
        await message.answer("Siz hali testni yakunlamagansiz. Testni boshlash uchun /start bosing.")
        return

    if user.status == UserStatus.NEW:
        text = (
            f"Testni yakunlagansiz. Natijangiz: {user.score} ta to'g'ri javob.\n\n"
            "Telefon raqamingizni hali yubormagansiz — iltimos, oldingi xabardagi tugma orqali yuboring."
        )
    elif user.status == UserStatus.PENDING:
        text = (
            f"Natijangiz: {user.score} ta to'g'ri javob.\n\n"
            "✅ Ma'lumotlaringiz qabul qilindi va tekshiruvda. "
            "G'oliblar aniqlanganda siz bilan bog'lanamiz."
        )
    elif user.status == UserStatus.APPROVED:
        text = (
            f"Natijangiz: {user.score} ta to'g'ri javob.\n\n"
            "🎉 Siz tasdiqlangansiz! Kodingiz tez orada yuboriladi."
        )
    elif user.status == UserStatus.CODE_SENT:
        winner_result = await session.execute(select(Winner).where(Winner.user_id == user.id))
        winner = winner_result.scalar_one_or_none()
        code = winner.redeem_code if winner else "-"
        text = (
            f"Natijangiz: {user.score} ta to'g'ri javob.\n\n"
            f"🎁 Tabriklaymiz! Sizga tasdiqlash kodi yuborilgan: {code}\n"
            "Sovg'angizni olish uchun shu kodni ko'rsating."
        )
    elif user.status == UserStatus.REDEEMED:
        text = (
            f"Natijangiz: {user.score} ta to'g'ri javob.\n\n"
            "✅ Sovg'angizni allaqachon olib bo'lgansiz. Ishtirokingiz uchun rahmat!"
        )
    elif user.status == UserStatus.REJECTED:
        text = (
            f"Natijangiz: {user.score} ta to'g'ri javob.\n\n"
            "Afsuski, bu safar siz tanlanmadingiz. Ishtirokingiz uchun rahmat!"
        )
    else:
        text = f"Natijangiz: {user.score} ta to'g'ri javob."

    await message.answer(text)
    logger.info("Status so'raldi: telegram_id=%s, status=%s", message.from_user.id, user.status)