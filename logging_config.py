import logging

from config import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Ba'zi kutubxonalar juda ko'p log yozadi, ularni kamaytiramiz
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
