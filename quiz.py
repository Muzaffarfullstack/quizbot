import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards import confirm_restart_keyboard, question_keyboard, request_phone_keyboard
from model import AnswerOption, Question, QuizAttempt, User
from service import AlreadyAttemptedError, QuizService
from states import QuizStates

logger = logging.getLogger(__name__)
router = Router(name="quiz")


@router.callback_query(F.data == "start_test")
async def start_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service = QuizService(session)
    user = await service.get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )

    if await service.has_existing_attempt(user):
        await callback.message.edit_text(
            "⚠️ Siz avval testni topshirgansiz.\n\n"
            "Agar yangi test boshlasangiz, oldingi natijangiz butunlay o'chib ketadi "
            "va faqat yangi natija saqlanadi. Bu qaytarib bo'lmaydigan amal.\n\n"
            "Rostdan ham qayta boshlaysizmi?",
            reply_markup=confirm_restart_keyboard(),
        )
        await callback.answer()
        return

    await _begin_quiz(callback, state, session, user)


@router.callback_query(F.data == "confirm_restart")
async def confirm_restart(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    service = QuizService(session)
    user = await service.get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        full_name=callback.from_user.full_name,
    )
    await service.reset_user_attempt(user)
    logger.info("User qayta test boshlashni tasdiqladi: telegram_id=%s", callback.from_user.id)
    await _begin_quiz(callback, state, session, user)


@router.callback_query(F.data == "cancel_restart")
async def cancel_restart(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Bekor qilindi. Oldingi natijangiz saqlanib qoldi.")
    await callback.answer()


async def _begin_quiz(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User) -> None:
    service = QuizService(session)
    try:
        attempt, questions = await service.start_attempt(user)
    except AlreadyAttemptedError:
        await callback.answer("Bir vaqtda ikki marta boshlanib ketdi, qaytadan urinib ko'ring.", show_alert=True)
        return
    except ValueError:
        await callback.answer("Hozircha faol savollar mavjud emas.", show_alert=True)
        return

    await state.update_data(
        attempt_id=attempt.id,
        question_ids=[q.id for q in questions],
        index=0,
    )
    await state.set_state(QuizStates.taking_quiz)

    await callback.message.edit_text(f"Test boshlandi!\nJami savollar: {len(questions)}")
    await _send_question(callback.message, questions[0], index=0, total=len(questions))
    await callback.answer()
    logger.info("Test boshlandi: telegram_id=%s, attempt_id=%s", callback.from_user.id, attempt.id)


async def _send_question(message: Message, question: Question, index: int, total: int) -> None:
    text = f"Savol {index + 1}/{total}:\n\n{question.question_text}"
    await message.answer(text, reply_markup=question_keyboard(question))


@router.callback_query(QuizStates.taking_quiz, F.data.startswith("answer:"))
async def process_answer(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    question_ids: list[int] = data.get("question_ids", [])
    index: int = data.get("index", 0)
    attempt_id = data.get("attempt_id")

    if index >= len(question_ids):
        await callback.answer()
        return

    question_result = await session.execute(select(Question).where(Question.id == question_ids[index]))
    question = question_result.scalar_one_or_none()

    attempt_result = await session.execute(select(QuizAttempt).where(QuizAttempt.id == attempt_id))
    attempt = attempt_result.scalar_one_or_none()

    if question is None or attempt is None:
        await callback.answer("Xatolik yuz berdi. Qaytadan /start bosing.", show_alert=True)
        await state.clear()
        return

    selected = AnswerOption(callback.data.split(":", 1)[1])
    service = QuizService(session)
    await service.submit_answer(attempt, question, selected)

    await callback.message.edit_text(f"{callback.message.text}\n\n✓ Javobingiz qabul qilindi.")
    await callback.answer()

    index += 1
    await state.update_data(index=index)

    if index < len(question_ids):
        next_question_result = await session.execute(
            select(Question).where(Question.id == question_ids[index])
        )
        next_question = next_question_result.scalar_one_or_none()
        if next_question is not None:
            await _send_question(callback.message, next_question, index=index, total=len(question_ids))
        return

    # Savollar tugadi -> testni yakunlash
    await _finish_quiz(callback, state, session, attempt)


async def _finish_quiz(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    attempt: QuizAttempt,
) -> None:
    service = QuizService(session)

    user_row = await session.execute(select(User).where(User.id == attempt.user_id))
    user = user_row.scalar_one_or_none()

    score = await service.finish_attempt(attempt, user)

    await callback.message.answer(f"🏁 Test yakunlandi!\n\nSizning natijangiz: {score} ta to'g'ri javob.")

    await state.set_state(QuizStates.waiting_for_phone)
    await callback.message.answer(
        "✅ Natijalaringiz qabul qilindi.\n\n"
        "G'oliblar aniqlanganda siz bilan bog'lanamiz. Iltimos, telefon raqamingizni yuboring.\n"
        "Faqat pastdagi tugma orqali yuborish mumkin (o'z raqamingiz avtomatik aniqlanadi).",
        reply_markup=request_phone_keyboard(),
    )
    logger.info("Telefon so'raldi: telegram_id=%s, score=%s", callback.from_user.id, score)