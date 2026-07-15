from aiogram.fsm.state import State, StatesGroup


class QuizStates(StatesGroup):
    taking_quiz = State()       # user savollarga javob berayotgan holat
    waiting_for_phone = State()  # test tugadi, telefon raqami kutilmoqda


class AddQuestionStates(StatesGroup):
    waiting_text = State()
    waiting_option_a = State()
    waiting_option_b = State()
    waiting_option_c = State()
    waiting_option_d = State()
    waiting_correct = State()
    waiting_category = State()
