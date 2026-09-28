from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.config import settings
from bot.database.db import async_session_maker
from bot.keyboards.inline import (
    get_confirm_start_inline,
    get_confirm_stop_inline,
    get_cancel_inline,
)
from bot.keyboards.reply import get_main_keyboard
from bot.services.generator_service import (
    GeneratorService,
    format_dt,
    format_duration,
    get_local_tz,
)

generator_router = Router()


class GeneratorFSM(StatesGroup):
    waiting_for_custom_start_time = State()
    waiting_for_custom_stop_time = State()
    waiting_for_stop_notes = State()


def parse_time_input(text: str) -> datetime:
    """Parses relative minutes (-15), HH:MM, or DD.MM.YYYY HH:MM into a UTC datetime."""
    text = text.strip()
    local_tz = get_local_tz()
    now_local = datetime.now(local_tz)

    # Relative minutes, e.g. -15 or 15 or "15 мин назад"
    clean_text = text.replace("мин", "").replace("назад", "").strip()
    if (clean_text.startswith("-") and clean_text[1:].isdigit()) or clean_text.isdigit():
        mins = abs(int(clean_text))
        target_local = now_local - timedelta(minutes=mins)
        return target_local.astimezone(timezone.utc).replace(tzinfo=None)

    # HH:MM format today
    if ":" in text and len(text) <= 5:
        parts = text.split(":")
        hour, minute = int(parts[0]), int(parts[1])
        target_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # If target is in the future compared to now by more than 1 min, maybe yesterday?
        if target_local > now_local + timedelta(minutes=2):
            target_local -= timedelta(days=1)
        return target_local.astimezone(timezone.utc).replace(tzinfo=None)

    # DD.MM.YYYY HH:MM or DD.MM HH:MM
    for fmt in ("%d.%m.%Y %H:%M", "%d.%m %H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            if fmt == "%d.%m %H:%M":
                parsed = parsed.replace(year=now_local.year)
            target_local = parsed.replace(tzinfo=local_tz)
            return target_local.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            pass

    raise ValueError("Неверный формат времени")


# --- START FLOW ---

@generator_router.message(F.text == "▶️ Запустить генератор")
async def msg_start_generator(message: Message):
    async with async_session_maker() as session:
        gen = await GeneratorService.get_state(session)

    if gen.is_running:
        start_str = format_dt(gen.current_start_time)
        op = gen.current_start_user_name or "Оператор"
        await message.answer(f"⚠️ Генератор уже запущен в {start_str} ({op})!")
        return

    text = (
        "❓ <b>Подтверждение запуска генератора</b>\n\n"
        f"• Текущий остаток топлива: <code>{gen.current_fuel:.1f} л</code>\n"
        f"• Наработка: <code>{gen.total_hours:.2f} мч</code>\n\n"
        "Запустить генератор прямо сейчас?"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_confirm_start_inline())


@generator_router.callback_query(F.data == "gen_start_confirm")
async def cb_start_confirm(callback: CallbackQuery):
    async with async_session_maker() as session:
        gen = await GeneratorService.get_state(session)

    if gen.is_running:
        start_str = format_dt(gen.current_start_time)
        await callback.answer(f"Генератор уже работает с {start_str}!", show_alert=True)
        return

    text = (
        "❓ <b>Подтверждение запуска генератора</b>\n\n"
        f"• Текущий остаток топлива: <code>{gen.current_fuel:.1f} л</code>\n"
        f"• Наработка: <code>{gen.total_hours:.2f} мч</code>\n\n"
        "Запустить генератор прямо сейчас?"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_confirm_start_inline())
    await callback.answer()


@generator_router.callback_query(F.data == "gen_start_now")
async def cb_start_now(callback: CallbackQuery, is_admin: bool = False):
    user = callback.from_user
    async with async_session_maker() as session:
        ok, msg, data = await GeneratorService.start_generator(
            session,
            user_id=user.id,
            user_name=user.full_name or user.username or "Оператор"
        )

    if not ok:
        await callback.message.edit_text(f"❌ {msg}")
        await callback.answer()
        return

    start_str = format_dt(data["start_time"])
    resp_text = (
        f"🟢 <b>ГЕНЕРАТОР ЗАПУЩЕН!</b>\n\n"
        f"🕒 <b>Время старта:</b> {start_str}\n"
        f"👤 <b>Оператор:</b> {data['operator']}\n"
        f"⛽ <b>Топливо в баке:</b> {data['current_fuel']:.1f} л\n"
        f"⏱ <b>Текущие моточасы:</b> {data['total_hours']:.2f} мч\n"
        f"🔧 <b>До планового ТО:</b> {data['hours_to_maint']:.2f} мч\n\n"
        f"<i>Не забудьте нажать «Остановить генератор» после завершения работы.</i>"
    )
    await callback.message.edit_text(resp_text, parse_mode="HTML")
    await callback.message.answer(
        "Статус обновлен в главном меню:",
        reply_markup=get_main_keyboard(is_running=True, is_admin=is_admin)
    )
    await callback.answer("Генератор запущен!")


@generator_router.callback_query(F.data == "gen_start_custom")
async def cb_start_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GeneratorFSM.waiting_for_custom_start_time)
    text = (
        "🕒 <b>Введите фактическое время запуска:</b>\n\n"
        "Примеры ввода:\n"
        "• <code>10:15</code> (сегодня в 10:15)\n"
        "• <code>-20</code> (20 минут назад)\n"
        "• <code>28.09 09:30</code> (дата и время)\n"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_cancel_inline())
    await callback.answer()


@generator_router.message(GeneratorFSM.waiting_for_custom_start_time)
async def process_custom_start_time(message: Message, state: FSMContext, is_admin: bool = False):
    try:
        custom_dt = parse_time_input(message.text)
    except Exception:
        await message.answer(
            "❌ Не удалось распознать время. Введите в формате <code>10:30</code> или <code>-15</code> (15 мин назад):",
            parse_mode="HTML",
            reply_markup=get_cancel_inline()
        )
        return

    await state.clear()
    user = message.from_user

    async with async_session_maker() as session:
        ok, msg, data = await GeneratorService.start_generator(
            session,
            user_id=user.id,
            user_name=user.full_name or user.username or "Оператор",
            custom_start_time=custom_dt
        )

    if not ok:
        await message.answer(f"❌ {msg}")
        return

    start_str = format_dt(data["start_time"])
    resp_text = (
        f"🟢 <b>ГЕНЕРАТОР ЗАПУЩЕН (с корректировкой времени)!</b>\n\n"
        f"🕒 <b>Время старта:</b> {start_str}\n"
        f"👤 <b>Оператор:</b> {data['operator']}\n"
        f"⛽ <b>Топливо в баке:</b> {data['current_fuel']:.1f} л\n"
        f"⏱ <b>Текущие моточасы:</b> {data['total_hours']:.2f} мч"
    )
    await message.answer(resp_text, parse_mode="HTML", reply_markup=get_main_keyboard(is_running=True, is_admin=is_admin))


# --- STOP FLOW ---

@generator_router.message(F.text == "⏹️ Остановить генератор")
async def msg_stop_generator(message: Message):
    async with async_session_maker() as session:
        dash_data = await GeneratorService.get_dashboard_data(session)

    if not dash_data["is_running"]:
        await message.answer("⚠️ Генератор сейчас не работает!")
        return

    duration_str = format_duration(dash_data["current_run_hours"])
    fuel_est = dash_data["current_run_hours"] * dash_data["fuel_rate"]

    text = (
        "❓ <b>Подтверждение остановки генератора</b>\n\n"
        f"🕒 <b>В работе с:</b> {format_dt(dash_data['current_start_time'])}\n"
        f"⏱ <b>Время работы:</b> {duration_str}\n"
        f"⛽ <b>Расчетный расход топлива:</b> ~{fuel_est:.1f} л\n\n"
        "Остановить генератор прямо сейчас?"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_confirm_stop_inline())


@generator_router.callback_query(F.data == "gen_stop_confirm")
async def cb_stop_confirm(callback: CallbackQuery):
    async with async_session_maker() as session:
        dash_data = await GeneratorService.get_dashboard_data(session)

    if not dash_data["is_running"]:
        await callback.answer("Генератор сейчас не работает!", show_alert=True)
        return

    duration_str = format_duration(dash_data["current_run_hours"])
    fuel_est = dash_data["current_run_hours"] * dash_data["fuel_rate"]

    text = (
        "❓ <b>Подтверждение остановки генератора</b>\n\n"
        f"🕒 <b>В работе с:</b> {format_dt(dash_data['current_start_time'])}\n"
        f"⏱ <b>Время работы:</b> {duration_str}\n"
        f"⛽ <b>Расчетный расход топлива:</b> ~{fuel_est:.1f} л\n\n"
        "Остановить генератор прямо сейчас?"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_confirm_stop_inline())
    await callback.answer()


@generator_router.callback_query(F.data == "gen_stop_now")
async def cb_stop_now(callback: CallbackQuery, is_admin: bool = False):
    user = callback.from_user
    async with async_session_maker() as session:
        ok, msg, data = await GeneratorService.stop_generator(
            session,
            user_id=user.id,
            user_name=user.full_name or user.username or "Оператор"
        )

    if not ok:
        await callback.message.edit_text(f"❌ {msg}")
        await callback.answer()
        return

    duration_str = format_duration(data["duration_hours"])
    maint_badge = f"{data['hours_to_maint']:.2f} мч"
    if data["hours_to_maint"] <= 0:
        maint_badge += " 🔴 <b>(ПРОСРОЧЕНО!)</b>"
    elif data["hours_to_maint"] <= 20:
        maint_badge += " 🟡 <b>(СКОРО ТО!)</b>"
    else:
        maint_badge += " 🟢"

    resp_text = (
        f"🔴 <b>ГЕНЕРАТОР ОСТАНОВЛЕН!</b>\n"
        f"────────────────────\n"
        f"⏱ <b>Время работы:</b> {duration_str}\n"
        f"🕒 <b>Интервал:</b> {format_dt(data['start_time'])} — {format_dt(data['stop_time'])}\n"
        f"⛽ <b>Израсходовано топлива:</b> <code>{data['fuel_consumed']:.2f} л</code>\n"
        f"📊 <b>Остаток в баке:</b> <code>{data['end_fuel']:.1f} л</code>\n"
        f"📈 <b>Общая наработка:</b> <code>{data['total_hours']:.2f} мч</code>\n"
        f"🔧 <b>До планового ТО:</b> {maint_badge}\n"
        f"👤 <b>Остановил:</b> {data['operator']}\n"
        f"────────────────────"
    )
    await callback.message.edit_text(resp_text, parse_mode="HTML")
    await callback.message.answer(
        "Статус обновлен в главном меню:",
        reply_markup=get_main_keyboard(is_running=False, is_admin=is_admin)
    )
    await callback.answer("Генератор остановлен!")


@generator_router.callback_query(F.data == "gen_stop_custom")
async def cb_stop_custom(callback: CallbackQuery, state: FSMContext):
    await state.set_state(GeneratorFSM.waiting_for_custom_stop_time)
    text = (
        "🕒 <b>Введите фактическое время остановки:</b>\n\n"
        "Примеры ввода:\n"
        "• <code>12:45</code> (сегодня в 12:45)\n"
        "• <code>-10</code> (10 минут назад)\n"
        "• <code>28.09 14:00</code> (дата и время)\n"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_cancel_inline())
    await callback.answer()


@generator_router.message(GeneratorFSM.waiting_for_custom_stop_time)
async def process_custom_stop_time(message: Message, state: FSMContext, is_admin: bool = False):
    try:
        custom_dt = parse_time_input(message.text)
    except Exception:
        await message.answer(
            "❌ Не удалось распознать время. Введите в формате <code>12:45</code> или <code>-10</code> (10 мин назад):",
            parse_mode="HTML",
            reply_markup=get_cancel_inline()
        )
        return

    await state.clear()
    user = message.from_user

    async with async_session_maker() as session:
        ok, msg, data = await GeneratorService.stop_generator(
            session,
            user_id=user.id,
            user_name=user.full_name or user.username or "Оператор",
            custom_stop_time=custom_dt
        )

    if not ok:
        await message.answer(f"❌ {msg}")
        return

    duration_str = format_duration(data["duration_hours"])
    resp_text = (
        f"🔴 <b>ГЕНЕРАТОР ОСТАНОВЛЕН (с корректировкой времени)!</b>\n"
        f"────────────────────\n"
        f"⏱ <b>Время работы:</b> {duration_str}\n"
        f"🕒 <b>Интервал:</b> {format_dt(data['start_time'])} — {format_dt(data['stop_time'])}\n"
        f"⛽ <b>Израсходовано топлива:</b> <code>{data['fuel_consumed']:.2f} л</code>\n"
        f"📊 <b>Остаток в баке:</b> <code>{data['end_fuel']:.1f} л</code>\n"
        f"📈 <b>Общая наработка:</b> <code>{data['total_hours']:.2f} мч</code>\n"
        f"🔧 <b>До планового ТО:</b> <code>{data['hours_to_maint']:.2f} мч</code>\n"
        f"────────────────────"
    )
    await message.answer(resp_text, parse_mode="HTML", reply_markup=get_main_keyboard(is_running=False, is_admin=is_admin))
