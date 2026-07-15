import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards import correct_answer_choice_keyboard, skip_category_keyboard
from model import AnswerOption, Question
from states import AddQuestionStates

logger = logging.getLogger(__name__)
router = Router(name="questions_admin")


# ---------- Savol qo'shish wizard ----------

@router.message(Command("addquestion"))
async def add_question_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AddQuestionStates.waiting_text)
    await message.answer(
        "📝 Yangi savol qo'shish.\n\n"
        "Savol matnini yuboring.\n"
        "Istalgan vaqtda /cancel yuborib bekor qilishingiz mumkin."
    )


@router.message(Command("cancel"), AddQuestionStates.waiting_text)
@router.message(Command("cancel"), AddQuestionStates.waiting_option_a)
@router.message(Command("cancel"), AddQuestionStates.waiting_option_b)
@router.message(Command("cancel"), AddQuestionStates.waiting_option_c)
@router.message(Command("cancel"), AddQuestionStates.waiting_option_d)
@router.message(Command("cancel"), AddQuestionStates.waiting_correct)
@router.message(Command("cancel"), AddQuestionStates.waiting_category)
async def cancel_add_question(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(AddQuestionStates.waiting_text, F.text)
async def add_question_text(message: Message, state: FSMContext) -> None:
    await state.update_data(question_text=message.text)
    await state.set_state(AddQuestionStates.waiting_option_a)
    await message.answer("A) variantini yuboring.")


@router.message(AddQuestionStates.waiting_option_a, F.text)
async def add_option_a(message: Message, state: FSMContext) -> None:
    await state.update_data(option_a=message.text)
    await state.set_state(AddQuestionStates.waiting_option_b)
    await message.answer("B) variantini yuboring.")


@router.message(AddQuestionStates.waiting_option_b, F.text)
async def add_option_b(message: Message, state: FSMContext) -> None:
    await state.update_data(option_b=message.text)
    await state.set_state(AddQuestionStates.waiting_option_c)
    await message.answer("C) variantini yuboring.")


@router.message(AddQuestionStates.waiting_option_c, F.text)
async def add_option_c(message: Message, state: FSMContext) -> None:
    await state.update_data(option_c=message.text)
    await state.set_state(AddQuestionStates.waiting_option_d)
    await message.answer("D) variantini yuboring.")


@router.message(AddQuestionStates.waiting_option_d, F.text)
async def add_option_d(message: Message, state: FSMContext) -> None:
    await state.update_data(option_d=message.text)
    await state.set_state(AddQuestionStates.waiting_correct)
    await message.answer(
        "To'g'ri javobni tanlang:",
        reply_markup=correct_answer_choice_keyboard(),
    )


@router.callback_query(AddQuestionStates.waiting_correct, F.data.startswith("correct:"))
async def add_correct_answer(callback: CallbackQuery, state: FSMContext) -> None:
    correct = callback.data.split(":", 1)[1]
    await state.update_data(correct_answer=correct)
    await state.set_state(AddQuestionStates.waiting_category)
    await callback.message.edit_text(f"To'g'ri javob: {correct.upper()} ✅")
    await callback.message.answer(
        "Kategoriya nomini yuboring (masalan: Kardiologiya), yoki o'tkazib yuborishingiz mumkin.",
        reply_markup=skip_category_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "addq_cancel")
async def add_question_cancel_cb(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


@router.callback_query(AddQuestionStates.waiting_category, F.data == "addq_skip_category")
async def add_category_skip(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await _save_question(callback.message, state, session, category=None)
    await callback.answer()


@router.message(AddQuestionStates.waiting_category, F.text)
async def add_category_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _save_question(message, state, session, category=message.text)


async def _save_question(message: Message, state: FSMContext, session: AsyncSession, category: str | None) -> None:
    data = await state.get_data()

    question = Question(
        question_text=data["question_text"],
        option_a=data["option_a"],
        option_b=data["option_b"],
        option_c=data["option_c"],
        option_d=data["option_d"],
        correct_answer=AnswerOption(data["correct_answer"]),
        category=category,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)

    await state.clear()
    await message.answer(
        f"✅ Savol qo'shildi (ID: {question.id}).\n\nYana savol qo'shish uchun /addquestion yuboring."
    )
    logger.info("Yangi savol qo'shildi: id=%s", question.id)


# ---------- Ro'yxat, o'chirish, yoqish/o'chirish ----------

@router.message(Command("questions"))
async def list_questions(message: Message, session: AsyncSession) -> None:
    result = await session.execute(select(Question).order_by(Question.id))
    questions = result.scalars().all()

    if not questions:
        await message.answer("Hozircha savollar yo'q. /addquestion orqali qo'shing.")
        return

    lines = []
    for q in questions:
        status = "🟢" if q.is_active else "🔴"
        preview = q.question_text[:40] + ("..." if len(q.question_text) > 40 else "")
        lines.append(f"{status} #{q.id}: {preview}")

    text = "\n".join(lines)
    text += (
        f"\n\nJami: {len(questions)} ta savol.\n\n"
        "/delquestion <id> — o'chirish\n"
        "/togglequestion <id> — yoqish/o'chirish"
    )
    await message.answer(text)


@router.message(Command("delquestion"))
async def delete_question(message: Message, command: CommandObject, session: AsyncSession) -> None:
    question_id = _parse_id(command.args)
    if question_id is None:
        await message.answer("Foydalanish: /delquestion <id>")
        return

    result = await session.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        await message.answer("Bunday ID topilmadi.")
        return

    await session.delete(question)
    await session.commit()
    await message.answer(f"🗑 Savol o'chirildi (ID: {question_id}).")


@router.message(Command("togglequestion"))
async def toggle_question(message: Message, command: CommandObject, session: AsyncSession) -> None:
    question_id = _parse_id(command.args)
    if question_id is None:
        await message.answer("Foydalanish: /togglequestion <id>")
        return

    result = await session.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        await message.answer("Bunday ID topilmadi.")
        return

    question.is_active = not question.is_active
    await session.commit()
    state_text = "yoqildi ✅" if question.is_active else "o'chirildi 🔴"
    await message.answer(f"Savol #{question_id} {state_text}.")


def _parse_id(args: str | None) -> int | None:
    if not args:
        return None
    try:
        return int(args.strip())
    except ValueError:
        return None
