from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Telegram ---
    BOT_TOKEN: str
    ADMIN_IDS: str = ""  # vergul bilan ajratilgan telegram_id lar, masalan: "123,456"

    # --- Database ---
    POSTGRES_USER: str = "quiz_user"
    POSTGRES_PASSWORD: str = "quiz_pass"
    POSTGRES_DB: str = "quiz_db"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: int = 5432

    # --- Admin panel (FastAPI) ---
    ADMIN_SECRET_KEY: str = "change-me-in-production"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change-me"
    ADMIN_HOST: str = "0.0.0.0"
    ADMIN_PORT: int = 8000

    # --- Quiz ---
    QUESTIONS_PER_ATTEMPT: int = 20
    MIN_CORRECT_FOR_PRIZE: int = 15  # shundan kam bo'lsa telefon so'ralmaydi

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy uchun asyncpg connection string."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def admin_ids_list(self) -> list[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()