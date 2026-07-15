import logging
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards import remove_keyboard
from states import QuizStates
from service import QuizService

logger = logging.getLogger(__name__)
router = Router(name="contact")


@router.message(QuizStates.waiting_for_phone, lambda message: message.contact is not None)
async def process_contact(message: Message, state: FSMContext, session: AsyncSession) -> None:
    contact = message.contact

    # Xavfsizlik tekshiruvi: faqat o'z raqamini yuborishi mumkin
    if contact.user_id != message.from_user.id:
        await message.answer("Bu sizning raqamingiz emas.")
        logger.warning(
            "Boshqa userning kontakti yuborilishga urinildi: sender=%s, contact_owner=%s",
            message.from_user.id,
            contact.user_id,
        )
        return

    service = QuizService(session)
    user = await service.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
    await service.set_phone(user, contact.phone_number)

    await message.answer(
        "✅ Raqamingiz qabul qilindi.\n\n"
        "Natijalar tekshirilmoqda.\n"
        "Agar g'olib bo'lsangiz admin siz bilan bog'lanadi.",
        reply_markup=remove_keyboard(),
    )
    await state.clear()
    logger.info("Telefon raqami qabul qilindi: telegram_id=%s", message.from_user.id)


@router.message(QuizStates.waiting_for_phone)
async def invalid_contact_input(message: Message) -> None:
    """Agar user matn yozsa yoki boshqa narsa yuborsa, tugmani qayta eslatadi."""
    await message.answer(
        "Iltimos, telefon raqamingizni yuborish uchun pastdagi tugmani bosing.",
        reply_markup=None,
    )