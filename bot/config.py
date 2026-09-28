from typing import List, Union, Any, Optional
from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram Bot
    BOT_TOKEN: str = ""
    ADMIN_IDS: Any = Field(default_factory=list)
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
        if v is None:
            return []
        if isinstance(v, (int, float)):
            return [int(v)]
        if isinstance(v, str):
            clean_str = v.strip().strip("'\"").strip()
            if not clean_str:
                return []
            result = []
            for item in clean_str.split(","):
                item = item.strip().strip("'\"").strip()
                if not item:
                    continue
                if item.isdigit() or (item.startswith("-") and item[1:].isdigit()):
                    result.append(int(item))
                else:
                    result.append(item.lstrip("@").lower())
            return result
        if isinstance(v, (list, set, tuple)):
            result = []
            for item in v:
                if isinstance(item, (int, float)):
                    result.append(int(item))
                elif isinstance(item, str):
                    clean = item.strip().strip("'\"").strip()
                    if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
                        result.append(int(clean))
                    elif clean:
                        result.append(clean.lstrip("@").lower())
            return result
        return []

    def is_admin(self, user_id: Union[int, str, None], username: Union[str, None] = None) -> bool:
        """Перевіряє, чи є користувач адміністратором за ID або username у налаштуваннях."""
        if not self.ADMIN_IDS:
            return False

        # Перевірка за числовим або рядковим user_id
        if user_id is not None:
            try:
                uid_int = int(user_id)
                if any(isinstance(x, int) and x == uid_int for x in self.ADMIN_IDS):
                    return True
            except (ValueError, TypeError):
                pass

            uid_str = str(user_id).strip()
            if any(str(x).strip() == uid_str for x in self.ADMIN_IDS):
                return True

        # Перевірка за Telegram username (без @, нечутливо до регістру)
        if username:
            clean_user = username.strip().lstrip("@").lower()
            if any(isinstance(x, str) and x.strip().lstrip("@").lower() == clean_user for x in self.ADMIN_IDS):
                return True

        return False


settings = Settings()
