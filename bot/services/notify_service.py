import asyncio
import logging
from datetime import datetime, timezone
from aiogram import Bot
from sqlalchemy import select

from bot.config import settings
from bot.database.db import async_session_maker
from bot.database.models import User
from bot.services.generator_service import GeneratorService, format_duration

logger = logging.getLogger(__name__)


async def background_monitoring_loop(bot: Bot):
    """Periodic background task checking runtime anomalies, fuel levels, and maintenance."""
    logger.info("Starting background monitoring loop...")
    while True:
        try:
            await asyncio.sleep(1800)  # Check every 30 minutes

            async with async_session_maker() as session:
                dash = await GeneratorService.get_dashboard_data(session)

                # Get all active operators and admins to notify
                users_res = await session.execute(
                    select(User).where(User.role.in_(["admin", "operator"]))
                )
                notify_users = users_res.scalars().all()
                if not notify_users:
                    continue

                # 1. Alert if generator is running continuously > 8 hours
                if dash["is_running"] and dash["current_run_hours"] >= 8.0:
                    dur_str = format_duration(dash["current_run_hours"])
                    msg = (
                        f"⚠️ <b>Внимание: длительная работа генератора!</b>\n\n"
                        f"Генератор работает непрерывно уже: <b>{dur_str}</b>.\n"
                        f"Остаток топлива: <code>{dash['current_fuel']:.1f} л</code> (~{dash['remaining_runtime_hours']:.1f} ч).\n"
                        f"Проверьте необходимость продолжения работы или дозаправки."
                    )
                    for u in notify_users:
                        try:
                            await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                        except Exception:
                            pass

                # 2. Critical fuel warning (< 15%)
                if dash["fuel_pct"] <= 15.0 and dash["is_running"]:
                    msg = (
                        f"🚨 <b>Критический остаток топлива!</b>\n\n"
                        f"В баке осталось: <code>{dash['current_fuel']:.1f} л</code> ({dash['fuel_pct']:.0f}%).\n"
                        f"Топлива хватит примерно на: <b>{dash['remaining_runtime_hours']:.1f} ч</b>.\n"
                        f"Срочно организуйте заправку генератора!"
                    )
                    for u in notify_users:
                        try:
                            await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                        except Exception:
                            pass

                # 3. Maintenance overdue warning
                if dash["hours_to_maint"] <= 0:
                    msg = (
                        f"🔧 <b>Внимание! Плановое ТО генератора просрочено!</b>\n\n"
                        f"Перепробег: <b>{abs(dash['hours_to_maint']):.1f} мч</b>.\n"
                        f"Пожалуйста, выполните регламентные работы и отметьте в боте."
                    )
                    for u in notify_users:
                        try:
                            await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                        except Exception:
                            pass

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in background monitoring loop: {e}", exc_info=True)
            await asyncio.sleep(60)
