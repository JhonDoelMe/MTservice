import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Bot
from sqlalchemy import select

from bot.config import settings
from bot.database.db import get_session_maker
from bot.database.models import User
from bot.services.generator_service import GeneratorService, format_duration

logger = logging.getLogger(__name__)


async def background_monitoring_loop(bot: Bot):
    """Періодичний фоновий моніторинг тривалості роботи, залишку пального та регламенту ТО."""
    logger.info("Запуск фонового циклу моніторингу генератора...")
    while True:
        try:
            await asyncio.sleep(1800)  # Перевірка кожні 30 хвилин

            session_maker = get_session_maker()
            async with session_maker() as session:
                dash = await GeneratorService.get_dashboard_data(session)

                users_res = await session.execute(
                    select(User).where(User.role.in_(["admin", "operator"]))
                )
                notify_users = users_res.scalars().all()
                if not notify_users:
                    continue

                # 1. Попередження про безперервну роботу > 8 годин
                if dash["is_running"] and dash["current_run_hours"] >= 8.0:
                    dur_str = format_duration(dash["current_run_hours"])
                    msg = (
                        f"⚠️ <b>Увага: тривала робота генератора!</b>\n\n"
                        f"Генератор працює безперервно вже: <b>{dur_str}</b>.\n"
                        f"Залишок пального: <code>{dash['current_fuel']:.1f} л</code> (~{dash['remaining_runtime_hours']:.1f} год).\n"
                        f"Перевірте необхідність продовження роботи або дозаправки."
                    )
                    for u in notify_users:
                        try:
                            await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                        except Exception:
                            pass

                # 2. Критичний залишок пального (< 15%)
                if dash["fuel_pct"] <= 15.0 and dash["is_running"]:
                    msg = (
                        f"🚨 <b>Критичний залишок пального!</b>\n\n"
                        f"У баку залишилося: <code>{dash['current_fuel']:.1f} л</code> ({dash['fuel_pct']:.0f}%).\n"
                        f"Пального вистачить приблизно на: <b>{dash['remaining_runtime_hours']:.1f} год</b>.\n"
                        f"Терміново організуйте заправку генератора!"
                    )
                    for u in notify_users:
                        try:
                            await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                        except Exception:
                            pass

                # 3. Прострочене ТО
                if dash["hours_to_maint"] <= 0:
                    msg = (
                        f"🔧 <b>Увага! Планове ТО генератора прострочено!</b>\n\n"
                        f"Перепробіг: <b>{abs(dash['hours_to_maint']):.1f} мч</b>.\n"
                        f"Будь ласка, виконайте регламентні роботи та зафіксуйте у диспетчерській."
                    )
                    for u in notify_users:
                        try:
                            await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                        except Exception:
                            pass

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Помилка фонового моніторингу: {e}", exc_info=True)
            await asyncio.sleep(60)
