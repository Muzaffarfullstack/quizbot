import logging
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def notify_approved(self, telegram_id: int) -> bool:
        text = (
            "🎉 Tabriklaymiz!\n\n"
            "Siz test g'olibi sifatida tasdiqlandingiz.\n\n"
            "Sovrin olish uchun siz bilan bog'lanamiz."
        )
        return await self._safe_send(telegram_id, text)

    async def notify_rejected(self, telegram_id: int) -> bool:
        text = "Natijalar bo'yicha siz g'olib sifatida tasdiqlanmadingiz."
        return await self._safe_send(telegram_id, text)

    async def notify_with_code(self, telegram_id: int, code: str) -> bool:
        text = (
            "🎉 Tabriklaymiz! Siz test g'olibi sifatida tasdiqlandingiz.\n\n"
            f"Sovg'angizni olish uchun quyidagi kodni ko'rsating:\n\n"
            f"<b>{code}</b>\n\n"
            "Diqqat: bu kod faqat bir marta ishlatiladi."
        )
        return await self._safe_send(telegram_id, text)

    async def _safe_send(self, telegram_id: int, text: str) -> bool:
        try:
            await self.bot.send_message(chat_id=telegram_id, text=text)
            return True
        except TelegramForbiddenError:
            logger.warning("User botni bloklagan: telegram_id=%s", telegram_id)
        except TelegramBadRequest as e:
            logger.error("Xabar yuborishda xatolik: telegram_id=%s, error=%s", telegram_id, e)
        return False