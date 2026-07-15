import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards import winner_review_keyboard
from model import User, UserStatus, Winner
from notifications import NotificationService
from service import QuizService

logger = logging.getLogger(__name__)
router = Router(name="admin")


@router.message(Command("winners"))
async def list_pending_winners(message: Message, session: AsyncSession) -> None:
    result = await session.execute(
        select(User).where(User.status == UserStatus.PENDING).order_by(User.score.desc())
    )
    users = result.scalars().all()

    if not users:
        await message.answer("Hozircha tekshiruv kutayotgan foydalanuvchilar yo'q.")
        return

    for user in users:
        masked_phone = _mask_phone(user.phone)
        text = (
            f"User:\n{user.full_name or '-'}\n\n"
            f"Telegram:\n@{user.username or '-'}\n\n"
            f"Phone:\n{masked_phone}\n\n"
            f"Score:\n{user.score}"
        )
        await message.answer(text, reply_markup=winner_review_keyboard(user.id))


def _mask_phone(phone: str | None) -> str:
    if not phone:
        return "-"
    if len(phone) <= 6:
        return phone
    return phone[:6] + "*" * (len(phone) - 6)


@router.callback_query(F.data.startswith("winner_approve:"))
async def approve_winner(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    user_id = int(callback.data.split(":", 1)[1])
    await _approve_and_send_code(callback, session, bot, user_id)


@router.callback_query(F.data.startswith("winner_reject:"))
async def reject_winner(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    user_id = int(callback.data.split(":", 1)[1])
    await _reject(callback, session, bot, user_id)


async def _approve_and_send_code(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    user_id: int,
) -> None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    service = QuizService(session)
    winner, code = await service.generate_and_send_code_data(user)
    winner.approved_by = callback.from_user.id

    from sqlalchemy import func as sa_func

    winner.approved_at = sa_func.now()
    await session.commit()

    notification_service = NotificationService(bot)
    await notification_service.notify_with_code(user.telegram_id, code)

    await callback.message.edit_text(
        f"{callback.message.text}\n\n— ✅ Tasdiqlandi, foydalanuvchiga kod yuborildi: {code}"
    )
    await callback.answer()
    logger.info("Winner approved, code sent: user_id=%s, code=%s", user_id, code)


async def _reject(
    callback: CallbackQuery,
    session: AsyncSession,
    bot: Bot,
    user_id: int,
) -> None:
    from sqlalchemy import func as sa_func

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    user.status = UserStatus.REJECTED

    winner_result = await session.execute(select(Winner).where(Winner.user_id == user_id))
    winner = winner_result.scalar_one_or_none()
    if winner is None:
        winner = Winner(user_id=user_id)
        session.add(winner)

    winner.status = UserStatus.REJECTED
    winner.approved_by = callback.from_user.id
    winner.approved_at = sa_func.now()

    await session.commit()

    notification_service = NotificationService(bot)
    await notification_service.notify_rejected(user.telegram_id)

    await callback.message.edit_text(f"{callback.message.text}\n\n— ❌ Rad etildi")
    await callback.answer()


@router.message(Command("redeem"))
async def redeem_code_command(message: Message, command: CommandObject, session: AsyncSession) -> None:
    """
    Admin sovg'a berish joyida userdan aytilgan kodni kiritadi:
    /redeem 482913
    """
    code = (command.args or "").strip()
    if not code:
        await message.answer("Foydalanish: /redeem <kod>\nMasalan: /redeem 482913")
        return

    service = QuizService(session)
    winner = await service.redeem_code(code, admin_telegram_id=message.from_user.id)

    if winner is None:
        await message.answer("❌ Kod noto'g'ri yoki allaqachon ishlatilgan.")
        return

    user_result = await session.execute(select(User).where(User.id == winner.user_id))
    user = user_result.scalar_one_or_none()
    name = user.full_name if user else "-"

    await message.answer(f"✅ Kod tasdiqlandi!\nFoydalanuvchi: {name}\nSovg'a berildi deb belgilandi.")
    logger.info("Code redeemed: code=%s, by_admin=%s", code, message.from_user.id)
