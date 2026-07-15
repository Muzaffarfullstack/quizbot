import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserStatus(str, enum.Enum):
    NEW = "new"              # hali testni boshlamagan / testda
    PENDING = "pending"      # test tugagan, telefon yuborilgan, tekshiruvda
    APPROVED = "approved"    # admin tasdiqladi (vaqtinchalik, kod yuborilguncha)
    REJECTED = "rejected"
    CODE_SENT = "code_sent"  # userga tasdiqlash kodi yuborildi, kelib olishini kutmoqda
    REDEEMED = "redeemed"    # sovg'a berildi, kod ishlatildi


class AnswerOption(str, enum.Enum):
    A = "a"
    B = "b"
    C = "c"
    D = "d"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.NEW
    )

    # Anti-cheat: bitta user faqat bitta marta test topshira oladi
    has_completed_test: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    attempts: Mapped[list["QuizAttempt"]] = relationship(back_populates="user")
    winner_record: Mapped["Winner | None"] = relationship(back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} tg_id={self.telegram_id} status={self.status}>"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(String(512), nullable=False)
    option_b: Mapped[str] = mapped_column(String(512), nullable=False)
    option_c: Mapped[str] = mapped_column(String(512), nullable=False)
    option_d: Mapped[str] = mapped_column(String(512), nullable=False)
    correct_answer: Mapped[AnswerOption] = mapped_column(
        Enum(AnswerOption, name="answer_option"), nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def get_option(self, key: AnswerOption) -> str:
        return {
            AnswerOption.A: self.option_a,
            AnswerOption.B: self.option_b,
            AnswerOption.C: self.option_c,
            AnswerOption.D: self.option_d,
        }[key]

    def __repr__(self) -> str:
        return f"<Question id={self.id} text={self.question_text[:30]!r}>"


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="attempts")
    answers: Mapped[list["Answer"]] = relationship(back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (
        # Anti-cheat: bir user uchun faqat bitta attempt bo'lishi kerak
        UniqueConstraint("user_id", name="uq_one_attempt_per_user"),
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))

    selected_answer: Mapped[AnswerOption] = mapped_column(Enum(AnswerOption, name="answer_option"))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)

    attempt: Mapped["QuizAttempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship()

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_one_answer_per_question"),
    )


class Winner(Base):
    __tablename__ = "winners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    approved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # admin telegram_id
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.PENDING
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sovg'ani olish uchun avtomatik generatsiya qilingan kod
    redeem_code: Mapped[str | None] = mapped_column(String(12), nullable=True, unique=True)
    code_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    redeemed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # kodni tasdiqlagan admin

    user: Mapped["User"] = relationship(back_populates="winner_record")