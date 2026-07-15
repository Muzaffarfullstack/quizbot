from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from model import AnswerOption, Question


def start_test_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Testni boshlash", callback_data="start_test")]
        ]
    )


def confirm_restart_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, qayta boshlash", callback_data="confirm_restart"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_restart"),
            ]
        ]
    )


def question_keyboard(question: Question) -> InlineKeyboardMarkup:
    options = [
        (AnswerOption.A, question.option_a),
        (AnswerOption.B, question.option_b),
        (AnswerOption.C, question.option_c),
        (AnswerOption.D, question.option_d),
    ]
    buttons = [
        [InlineKeyboardButton(text=f"{key.value.upper()}) {text}", callback_data=f"answer:{key.value}")]
        for key, text in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def request_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamimni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def winner_review_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"winner_approve:{user_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"winner_reject:{user_id}"),
            ]
        ]
    )


def correct_answer_choice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="A", callback_data="correct:a"),
                InlineKeyboardButton(text="B", callback_data="correct:b"),
                InlineKeyboardButton(text="C", callback_data="correct:c"),
                InlineKeyboardButton(text="D", callback_data="correct:d"),
            ],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="addq_cancel")],
        ]
    )


def skip_category_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="O'tkazib yuborish", callback_data="addq_skip_category")]]
    )