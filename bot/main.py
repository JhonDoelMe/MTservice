import asyncio
import logging
import sys

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from bot.config import settings
from bot.database.db import init_db
from bot.database.cache import cache
from bot.handlers import setup_routers
from bot.middlewares import AuthMiddleware
from bot.services.notify_service import background_monitoring_loop
from bot.logging_config import setup_logging
from webapp.server import app as webapp_app

setup_logging()
logger = logging.getLogger(__name__)


async def configure_bot_menu(bot: Bot):
    commands = [
        BotCommand(command="start", description="📱 Відкрити диспетчерську генератора"),
        BotCommand(command="help", description="📖 Довідка та інструкція"),
    ]
    await bot.set_my_commands(commands)

    # Встановлення нативної кнопки Telegram WebApp меню в лівому кутку чату
    webapp_url = settings.WEBAPP_URL or f"http://localhost:{settings.WEB_PORT}"
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="⚡ Генератор",
                web_app=WebAppInfo(url=webapp_url)
            )
        )
        logger.info(f"Встановлено кнопку меню Mini App: {webapp_url}")
    except Exception as e:
        logger.warning(f"Не вдалося встановити Chat Menu Button: {e}")


async def main():
    logger.info("Ініціалізація бази даних та кешу...")
    await init_db()

    # Створення конфігурації веб-сервера Uvicorn (FastAPI Mini App)
    config = uvicorn.Config(
        app=webapp_app,
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)

    # Якщо токен не вказаний, запускаємо тільки веб-сервер Mini App (режим веб-інтерфейсу)
    if not settings.BOT_TOKEN or settings.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or settings.BOT_TOKEN.startswith("1234567890"):
        logger.warning("BOT_TOKEN не задано. Запуск виключно веб-інтерфейсу Telegram Mini App...")
        print("\n" + "=" * 65)
        print(f"🌐 Telegram Mini App доступний за адресою: http://localhost:{settings.WEB_PORT}")
        print("💡 Вкажіть дійсний BOT_TOKEN у файлі .env для повноцінної інтеграції з Telegram")
        print("=" * 65 + "\n")
        await server.serve()
        return

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    setup_routers(dp)

    await configure_bot_menu(bot)

    bg_task = asyncio.create_task(background_monitoring_loop(bot))

    logger.info(f"Веб-інтерфейс Mini App запущено на http://{settings.WEB_HOST}:{settings.WEB_PORT}")
    logger.info("Запуск Telegram бота (polling)...")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        # Запускаємо одночасно сервер Mini App та бота в єдиному асинхронному циклі
        await asyncio.gather(
            server.serve(),
            dp.start_polling(bot)
        )
    finally:
        bg_task.cancel()
        await bot.session.close()
        await cache.close()
        logger.info("Сервіс успішно зупинено.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Процес завершено користувачем.")
