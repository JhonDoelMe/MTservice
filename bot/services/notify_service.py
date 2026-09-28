import asyncio
import logging
from datetime import datetime, timezone
import re
import httpx
from aiogram import Bot
from sqlalchemy import select

from bot.config import settings
from bot.database.db import get_session_maker
from bot.database.models import User, GeneratorState
from bot.services.generator_service import GeneratorService, format_duration, get_local_tz

logger = logging.getLogger(__name__)

async def fetch_minfin_fuel_price(fuel_type: str) -> float:
    """Парсить ціну палива з Мінфіну (Дніпропетровська область)."""
    try:
        url = "https://index.minfin.com.ua/markets/fuel/reg/dnepropetrovskaya/"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
            
            # fuel_type: "ДП", "А-95", "А-92", "Газ"
            search_type = fuel_type.replace("Бензин ", "")
            # Знаходимо рядок з цим паливом
            # На Мінфіні зазвичай `<td>ДП</td><td class="num">52,40</td>` або схоже
            match = re.search(rf'<td>{re.escape(search_type)}</td>.*?<td[^>]*>([\d,\.]+)</td>', html, re.IGNORECASE | re.DOTALL)
            if match:
                price_str = match.group(1).replace(',', '.')
                return float(price_str)
            else:
                logger.warning(f"Minfin scraper: {search_type} not found in HTML.")
    except Exception as e:
        logger.error(f"Minfin scraper error: {e}")
    return 0.0

async def background_monitoring_loop(bot: Bot):
    """Періодичний фоновий моніторинг тривалості роботи, залишку пального, регламенту ТО та робочого графіка."""
    logger.info("Запуск фонового циклу моніторингу генератора...")
    last_30m_check = 0
    last_daily_price_check = None
    notified_10m_date = None
    notified_end_date = None

    while True:
        try:
            await asyncio.sleep(60)  # Перевірка щохвилини

            session_maker = get_session_maker()
            async with session_maker() as session:
                dash = await GeneratorService.get_dashboard_data(session)
                
                local_now = datetime.now(get_local_tz())
                today_str = local_now.strftime("%Y-%m-%d")
                
                # --- 0. ПАРСИНГ МІНФІНУ (Раз на добу вранці ~08:00) ---
                if dash.get("auto_update_price") and local_now.hour >= 8 and last_daily_price_check != today_str:
                    last_daily_price_check = today_str
                    new_price = await fetch_minfin_fuel_price(dash.get("fuel_type", "ДП"))
                    if new_price > 0 and new_price != dash.get("fuel_price"):
                        gen = await session.get(GeneratorState, 1)
                        if gen:
                            gen.fuel_price = new_price
                            await session.commit()
                            logger.info(f"💰 Ціну палива автоматично оновлено: {new_price} ₴/л")

                users_res = await session.execute(
                    select(User).where(User.role.in_(["admin", "operator"]))
                )
                notify_users = users_res.scalars().all()
                if not notify_users:
                    continue

                # --- 1. ПЕРЕВІРКА ГРАФІКА РОБОТИ ТА НАГАДУВАННЯ ЗА 10 ХВ ДО ЗУПИНКИ ---
                if settings.WORK_HOURS_ENABLED and dash["is_running"]:
                    try:
                        end_parts = [int(p) for p in settings.WORK_END_TIME.split(":")]
                        end_mins_of_day = end_parts[0] * 60 + end_parts[1]
                        curr_mins_of_day = local_now.hour * 60 + local_now.minute
                        diff_mins = end_mins_of_day - curr_mins_of_day

                        # Нагадування рівно за 10 хвилин до закінчення робочого часу
                        if 9 <= diff_mins <= 10 and notified_10m_date != today_str:
                            notified_10m_date = today_str
                            msg = (
                                f"⏰ <b>Увага! Наближається кінець робочого часу!</b>\n\n"
                                f"Генератор зараз працює. До кінця дозволеного графіка залишилося <b>10 хвилин</b> (зупинка о {settings.WORK_END_TIME}).\n"
                                f"Будь ласка, підготуйтеся до зупинки генератора."
                            )
                            for u in notify_users:
                                try:
                                    await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                                except Exception:
                                    pass

                        # Попередження, якщо робочий час закінчився, а генератор досі ввімкнено
                        if diff_mins <= 0 and diff_mins >= -10 and notified_end_date != today_str:
                            notified_end_date = today_str
                            msg = (
                                f"🚨 <b>Увага! Робочий час закінчився о {settings.WORK_END_TIME}!</b>\n\n"
                                f"Генератор досі знаходиться в роботі. Необхідно терміново зупинити генератор згідно з регламентом."
                            )
                            for u in notify_users:
                                try:
                                    await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                                except Exception:
                                    pass
                    except Exception as err:
                        logger.error(f"Помилка розрахунку графіка: {err}")

                # --- 2. ПЕРЕВІРКИ КОЖНІ 30 ХВИЛИН ---
                import time
                now_ts = time.time()
                if now_ts - last_30m_check >= 1800:
                    last_30m_check = now_ts

                    # Попередження про безперервну роботу > 8 годин
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

                    # Критичний залишок пального (< 15%)
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

                    # Прострочене ТО
                    if dash["hours_to_maint"] <= 0:
                        msg = (
                            f"🔧 <b>Увага! Планове ТО генератора прострочено!</b>\n\n"
                            f"Перепробіг: <b>{abs(dash['hours_to_maint']):.1f} мч</b>.\n"
                            f"Будь ласка, виконайте регламентні роботи та зафіксуйте у додатку."
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
            await asyncio.sleep(30)
