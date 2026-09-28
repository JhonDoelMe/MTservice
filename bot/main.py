import asyncio
import logging
import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from bot.config import settings
from bot.database.db import init_db
from bot.handlers import setup_routers
from bot.middlewares import AuthMiddleware
from bot.services.notify_service import background_monitoring_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="status", description="📊 Текущий статус генератора"),
        BotCommand(command="help", description="📖 Справка и помощь"),
    ]
    await bot.set_my_commands(commands)


async def main():
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error(
            "ОШИБКА: Токен бота не задан! Пожалуйста, укажите валидный BOT_TOKEN в файле .env"
        )
        print("\n" + "=" * 60)
        print("⚠️  ВНИМАНИЕ: Необходимо указать BOT_TOKEN в файле .env")
        print("1. Откройте файл .env")
        print("2. Вставьте ваш токен Telegram бота, полученный у @BotFather")
        print("3. Укажите ваш Telegram ID в ADMIN_IDS (узнать можно у @userinfobot)")
        print("=" * 60 + "\n")
        return

    logger.info("Инициализация базы данных...")
    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Middlewares
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Handlers
    setup_routers(dp)

    await set_bot_commands(bot)

    # Start background task
    bg_task = asyncio.create_task(background_monitoring_loop(bot))

    logger.info("Запуск Telegram бота (polling)...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        bg_task.cancel()
        await bot.session.close()
        logger.info("Бот успешно остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Процесс завершен.")
