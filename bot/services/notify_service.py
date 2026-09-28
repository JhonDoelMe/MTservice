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
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

            matches = re.findall(r'<td[^>]*align=[\'\"]left[\'\"][^>]*>([\s\S]*?)</td>\s*<td[^>]*align=[\'\"]right[\'\"][^>]*>\s*<big>([\d,\.]+)</big>', html)
            target = (fuel_type or "").lower()
            for td, big in matches:
                clean_td = re.sub(r'<[^>]+>', '', td).strip().lower()
                price = float(big.replace(',', '.'))
                if ("дп" in target or "диз" in target) and ("дизел" in clean_td or "дп" in clean_td):
                    return price
                elif "95" in target and "95" in clean_td and "прем" not in clean_td:
                    return price
                elif "92" in target and "92" in clean_td:
                    return price
                elif "газ" in target and "газ" in clean_td:
                    return price

            logger.warning(f"Minfin scraper: {fuel_type} not matched in table.")
    except Exception as e:
        logger.error(f"Minfin scraper error: {e}")
    return 0.0

async def background_monitoring_loop(bot: Bot):
    """Періодичний фоновий моніторинг тривалості роботи, залишку пального, регламенту ТО та робочого графіка."""
    logger.info("Запуск фонового циклу моніторингу генератора...")
    # Per-generator state tracking (keyed by gen_id)
    last_30m_check = {}      # {gen_id: timestamp}
    last_daily_price_check = {}  # {gen_id: date_str}
    notified_10m_date = {}   # {gen_id: date_str}
    notified_end_date = {}   # {gen_id: date_str}

    while True:
        try:
            await asyncio.sleep(60)  # Перевірка щохвилини

            session_maker = get_session_maker()
            async with session_maker() as session:
                generators = await session.execute(select(GeneratorState))
                all_gens = generators.scalars().all()
                
                users_res = await session.execute(
                    select(User).where(User.role.in_(["admin", "operator"]))
                )
                notify_users = users_res.scalars().all()
                if not notify_users:
                    continue

                for gen_state in all_gens:
                    gen_id = gen_state.id
                    dash = await GeneratorService.get_dashboard_data(session, gen_id=gen_id)
                    
                    local_now = datetime.now(get_local_tz())
                    today_str = local_now.strftime("%Y-%m-%d")
                    
                    # --- 0. ПАРСИНГ МІНФІНУ (Раз на добу вранці ~08:00) ---
                    if dash.get("auto_update_price") and local_now.hour >= 8 and last_daily_price_check.get(gen_id) != today_str:
                        last_daily_price_check[gen_id] = today_str
                        new_price = await fetch_minfin_fuel_price(dash.get("fuel_type", "ДП"))
                        if new_price > 0 and new_price != dash.get("fuel_price"):
                            gen = await session.get(GeneratorState, gen_id)
                            if gen:
                                gen.fuel_price = new_price
                                await session.commit()
                                logger.info(f"💰 Ціну палива автоматично оновлено: {new_price} ₴/л")

                    # --- 1. ПЕРЕВІРКА ГРАФІКА РОБОТИ ТА НАГАДУВАННЯ ЗА 10 ХВ ДО ЗУПИНКИ ---
                    if settings.WORK_HOURS_ENABLED and dash["is_running"]:
                        try:
                            end_parts = [int(p) for p in settings.WORK_END_TIME.split(":")]
                            end_mins_of_day = end_parts[0] * 60 + end_parts[1]
                            curr_mins_of_day = local_now.hour * 60 + local_now.minute
                            diff_mins = end_mins_of_day - curr_mins_of_day

                            # Нагадування рівно за 10 хвилин до закінчення робочого часу
                            if 9 <= diff_mins <= 10 and notified_10m_date.get(gen_id) != today_str:
                                notified_10m_date[gen_id] = today_str
                                msg = (
                                    f"⏰ <b>[{dash.get('name', 'Генератор')}] Наближається кінець робочого часу!</b>\n\n"
                                    f"Генератор зараз працює. До кінця дозволеного графіка залишилося <b>10 хвилин</b> (зупинка о {settings.WORK_END_TIME}).\n"
                                    f"Будь ласка, підготуйтеся до зупинки генератора."
                                )
                                for u in notify_users:
                                    try:
                                        await bot.send_message(chat_id=u.user_id, text=msg, parse_mode="HTML")
                                    except Exception:
                                        pass

                            # Попередження, якщо робочий час закінчився, а генератор досі ввімкнено
                            if diff_mins <= 0 and diff_mins >= -10 and notified_end_date.get(gen_id) != today_str:
                                notified_end_date[gen_id] = today_str
                                msg = (
                                    f"🚨 <b>[{dash.get('name', 'Генератор')}] Робочий час закінчився о {settings.WORK_END_TIME}!</b>\n\n"
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
                    if now_ts - last_30m_check.get(gen_id, 0) >= 1800:
                        last_30m_check[gen_id] = now_ts

                        # Попередження про безперервну роботу > 8 годин
                        if dash["is_running"] and dash["current_run_hours"] >= 8.0:
                            dur_str = format_duration(dash["current_run_hours"])
                            msg = (
                                f"⚠️ <b>[{dash.get('name', 'Генератор')}] Тривала робота!</b>\n\n"
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
                                f"🚨 <b>[{dash.get('name', 'Генератор')}] Критичний залишок пального!</b>\n\n"
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
                                f"🔧 <b>[{dash.get('name', 'Генератор')}] Планове ТО прострочено!</b>\n\n"
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
