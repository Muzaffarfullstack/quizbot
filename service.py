import logging
import random
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from model import (
    Answer,
    AnswerOption,
    Question,
    QuizAttempt,
    User,
    UserStatus,
    Winner,
)

logger = logging.getLogger(__name__)


class AlreadyAttemptedError(Exception):
    """User allaqachon testni topshirgan bo'lsa ko'tariladi."""


class QuizService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(self, telegram_id: int, username: str | None, full_name: str | None) -> User:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, username=username, full_name=full_name)
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)
            logger.info("Yangi user yaratildi: telegram_id=%s", telegram_id)
        return user

    async def has_existing_attempt(self, user: User) -> bool:
        """User avval test topshirganmi yoki hozir faol attempt bormi - tekshiradi."""
        if user.has_completed_test:
            return True
        result = await self.session.execute(
            select(QuizAttempt).where(QuizAttempt.user_id == user.id)
        )
        return result.scalar_one_or_none() is not None

    async def reset_user_attempt(self, user: User) -> None:
        """
        Eski attempt va unga bog'liq javoblarni o'chiradi, user holatini
        'yangidan boshlash mumkin' holatiga qaytaradi. Telefon/winner
        ma'lumotlariga tegmaydi - ular alohida oqim orqali boshqariladi.
        """
        result = await self.session.execute(
            select(QuizAttempt).where(QuizAttempt.user_id == user.id)
        )
        old_attempt = result.scalar_one_or_none()
        if old_attempt is not None:
            await self.session.delete(old_attempt)

        user.has_completed_test = False
        user.score = 0
        await self.session.commit()
        logger.info("Eski attempt tozalandi, user qayta test boshlashi mumkin: user_id=%s", user.id)

    async def start_attempt(self, user: User) -> tuple[QuizAttempt, list[Question]]:
        """
        Yangi quiz attempt boshlaydi. Chaqiruvchi (quiz.py) bu funksiyani
        faqat eski attempt yo'qligiga ishonch hosil qilgandan keyin
        (yoki reset_user_attempt chaqirgandan keyin) chaqirishi kerak.
        """
        questions = await self._pick_random_questions(settings.QUESTIONS_PER_ATTEMPT)
        if not questions:
            raise ValueError("Bazada faol savollar mavjud emas.")

        attempt = QuizAttempt(user_id=user.id)
        self.session.add(attempt)
        try:
            await self.session.commit()
        except IntegrityError:
            # Race condition: ikkita so'rov bir vaqtda kelsa, unique constraint saqlaydi
            await self.session.rollback()
            raise AlreadyAttemptedError("Bu user uchun attempt allaqachon mavjud.")

        await self.session.refresh(attempt)
        return attempt, questions

    async def _pick_random_questions(self, limit: int) -> list[Question]:
        result = await self.session.execute(select(Question).where(Question.is_active.is_(True)))
        all_questions = list(result.scalars().all())
        random.shuffle(all_questions)
        return all_questions[:limit]

    async def submit_answer(
        self,
        attempt: QuizAttempt,
        question: Question,
        selected: AnswerOption,
    ) -> bool:
        """Javobni saqlaydi va to'g'ri/noto'g'ri ekanini qaytaradi."""
        is_correct = selected == question.correct_answer

        answer = Answer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_answer=selected,
            is_correct=is_correct,
        )
        self.session.add(answer)

        if is_correct:
            attempt.score += 1

        await self.session.commit()
        return is_correct

    async def finish_attempt(self, attempt: QuizAttempt, user: User) -> int:
        """Testni yakunlaydi, foydalanuvchi holatini yangilaydi, ballni qaytaradi."""
        from sqlalchemy import func as sa_func

        attempt.finished_at = sa_func.now()
        user.score = attempt.score
        user.has_completed_test = True

        await self.session.commit()
        return attempt.score

    async def get_current_question_index(self, attempt: QuizAttempt) -> int:
        result = await self.session.execute(select(Answer).where(Answer.attempt_id == attempt.id))
        return len(result.scalars().all())

    async def set_phone(self, user: User, phone: str) -> None:
        user.phone = phone
        user.status = UserStatus.PENDING
        await self.session.commit()

    @staticmethod
    def is_eligible_for_prize(score: int) -> bool:
        return score >= settings.MIN_CORRECT_FOR_PRIZE

    async def generate_and_send_code_data(self, user: User) -> tuple[Winner, str]:
        """
        Winner yozuvini yaratadi (yoki topadi) va unga unikal redeem_code
        biriktiradi. Xabar yuborishning o'zi NotificationService orqali,
        chaqiruvchi tomonda amalga oshiriladi.
        """
        result = await self.session.execute(select(Winner).where(Winner.user_id == user.id))
        winner = result.scalar_one_or_none()
        if winner is None:
            winner = Winner(user_id=user.id)
            self.session.add(winner)

        code = self._generate_unique_code()
        winner.status = UserStatus.CODE_SENT
        winner.redeem_code = code
        winner.code_sent_at = datetime.now(timezone.utc)

        user.status = UserStatus.CODE_SENT

        await self.session.commit()
        await self.session.refresh(winner)
        return winner, code

    def _generate_unique_code(self) -> str:
        # 6 xonali kod, masalan "482913"
        return f"{secrets.randbelow(900000) + 100000}"

    async def redeem_code(self, code: str, admin_telegram_id: int) -> Winner | None:
        """
        Kodni tekshiradi. Agar to'g'ri va hali ishlatilmagan bo'lsa,
        REDEEMED holatiga o'tkazadi va Winner qaytaradi. Aks holda None.
        """
        result = await self.session.execute(select(Winner).where(Winner.redeem_code == code))
        winner = result.scalar_one_or_none()
        if winner is None or winner.status != UserStatus.CODE_SENT:
            return None

        winner.status = UserStatus.REDEEMED
        winner.redeemed_at = datetime.now(timezone.utc)
        winner.redeemed_by = admin_telegram_id

        user_result = await self.session.execute(select(User).where(User.id == winner.user_id))
        user = user_result.scalar_one_or_none()
        if user is not None:
            user.status = UserStatus.REDEEMED

        await self.session.commit()
        await self.session.refresh(winner)
        return winner