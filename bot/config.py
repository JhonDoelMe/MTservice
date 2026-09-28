from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    BOT_TOKEN: str = ""
    ADMIN_IDS: Union[List[int], str] = []
    WEBAPP_URL: str = "http://localhost:8080"  # Зовнішній HTTPS URL для Telegram Mini App (наприклад з ngrok, cloudflare або домену)

    # Локалізація (Тільки Україна)
    TIMEZONE: str = "Europe/Kyiv"
    CURRENCY: str = "₴"

    # База даних (PostgreSQL) та кеш (Redis)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mtservice"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Веб-сервер Mini App (FastAPI)
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8080

    # Початкові параметри генератора (дефолтні значення для об'єкта)
    GENERATOR_NAME: str = "Основний ДГУ"
    INITIAL_TOTAL_HOURS: float = 0.0
    FUEL_RATE_PER_HOUR: float = 4.5  # літрів на годину
    TANK_CAPACITY: float = 150.0      # літрів
    INITIAL_FUEL_LEVEL: float = 100.0 # літрів
    MAINTENANCE_INTERVAL_HOURS: float = 250.0  # мотогодин між ТО
    MAINTENANCE_WARNING_HOURS: float = 20.0    # попереджати за 20 мч

    # Графік дозволеної роботи генератора (Київський час)
    WORK_HOURS_ENABLED: bool = True
    WORK_START_TIME: str = "08:00"
    WORK_END_TIME: str = "20:00"

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        if isinstance(v, (list, set, tuple)):
            return [int(x) for x in v]
        return []


settings = Settings()
