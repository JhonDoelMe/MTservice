from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    BOT_TOKEN: str = ""
    ADMIN_IDS: Union[List[int], str] = []
    TIMEZONE: str = "Europe/Moscow"
    DATABASE_URL: str = "sqlite+aiosqlite:///data/generator.db"

    # Generator defaults
    GENERATOR_NAME: str = "Основной ДГУ"
    INITIAL_TOTAL_HOURS: float = 0.0
    FUEL_RATE_PER_HOUR: float = 4.5
    TANK_CAPACITY: float = 150.0
    INITIAL_FUEL_LEVEL: float = 100.0
    MAINTENANCE_INTERVAL_HOURS: float = 250.0
    MAINTENANCE_WARNING_HOURS: float = 20.0

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
