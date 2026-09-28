from datetime import datetime, timedelta, timezone
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from sqlalchemy import select

from bot.database.db import async_session_maker
from bot.database.models import RunLog, FuelLog
from bot.keyboards.inline import get_reports_inline
from bot.services.excel_service import ExcelService
from bot.services.generator_service import (
    GeneratorService,
    format_dt,
    format_duration,
    get_local_tz,
)

reports_router = Router()


@reports_router.message(F.text == "📈 Отчеты")
async def msg_reports_menu(message: Message):
    async with async_session_maker() as session:
        dash = await GeneratorService.get_dashboard_data(session)

    text = (
        "📈 <b>Аналитика и отчетность по генератору</b>\n\n"
        f"• Всего наработка: <code>{dash['total_hours']:.2f} мч</code>\n"
        f"• Текущий остаток топлива: <code>{dash['current_fuel']:.1f} л</code>\n"
        f"• Норма расхода: <code>{dash['fuel_rate']:.1f} л/ч</code>\n\n"
        "Выберите нужный отчет или выгрузите файл Excel:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_reports_inline())


@reports_router.callback_query(F.data == "report_today")
async def cb_report_today(callback: CallbackQuery):
    local_tz = get_local_tz()
    now_local = datetime.now(local_tz)
    start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_day_utc = start_of_day_local.astimezone(timezone.utc).replace(tzinfo=None)

    async with async_session_maker() as session:
        res = await session.execute(
            select(RunLog).where(RunLog.stop_time >= start_of_day_utc).order_by(RunLog.id.desc())
        )
        runs = res.scalars().all()

        fuel_res = await session.execute(
            select(FuelLog).where(FuelLog.timestamp >= start_of_day_utc).order_by(FuelLog.id.desc())
        )
        fuels = fuel_res.scalars().all()

    total_duration = sum(r.duration_hours for r in runs)
    total_fuel = sum(r.fuel_consumed for r in runs)
    refuel_amount = sum(f.amount_liters for f in fuels)

    text = (
        f"📊 <b>Отчет за сегодня ({now_local.strftime('%d.%m.%Y')}):</b>\n"
        f"────────────────────\n"
        f"• Количество запусков: <b>{len(runs)}</b>\n"
        f"• Время работы: <b>{format_duration(total_duration)}</b>\n"
        f"• Израсходовано топлива: <b>{total_fuel:.2f} л</b>\n"
        f"• Заправлено топлива: <b>{refuel_amount:.1f} л</b>\n"
        f"────────────────────"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_reports_inline())
    await callback.answer()


@reports_router.callback_query(F.data == "report_month")
async def cb_report_month(callback: CallbackQuery):
    local_tz = get_local_tz()
    now_local = datetime.now(local_tz)
    start_of_month_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_month_utc = start_of_month_local.astimezone(timezone.utc).replace(tzinfo=None)

    async with async_session_maker() as session:
        res = await session.execute(
            select(RunLog).where(RunLog.stop_time >= start_of_month_utc).order_by(RunLog.id.desc())
        )
        runs = res.scalars().all()

        fuel_res = await session.execute(
            select(FuelLog).where(FuelLog.timestamp >= start_of_month_utc).order_by(FuelLog.id.desc())
        )
        fuels = fuel_res.scalars().all()

    total_duration = sum(r.duration_hours for r in runs)
    total_fuel = sum(r.fuel_consumed for r in runs)
    refuel_amount = sum(f.amount_liters for f in fuels)

    text = (
        f"📅 <b>Отчет за текущий месяц ({now_local.strftime('%m.%Y')}):</b>\n"
        f"────────────────────\n"
        f"• Всего запусков: <b>{len(runs)}</b>\n"
        f"• Общее время работы: <b>{format_duration(total_duration)}</b>\n"
        f"• Всего израсходовано: <b>{total_fuel:.2f} л</b>\n"
        f"• Всего заправлено: <b>{refuel_amount:.1f} л</b>\n"
        f"────────────────────"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_reports_inline())
    await callback.answer()


@reports_router.callback_query(F.data == "report_runs_last10")
async def cb_report_runs_last10(callback: CallbackQuery):
    async with async_session_maker() as session:
        res = await session.execute(
            select(RunLog).order_by(RunLog.id.desc()).limit(10)
        )
        runs = res.scalars().all()

    if not runs:
        await callback.message.edit_text(
            "📜 <b>Журнал запусков пуст</b>",
            parse_mode="HTML",
            reply_markup=get_reports_inline()
        )
        await callback.answer()
        return

    lines = ["📜 <b>Последние запуски генератора:</b>\n"]
    for r in runs:
        start_str = format_dt(r.start_time)
        dur = format_duration(r.duration_hours)
        lines.append(
            f"• <b>{start_str}</b>: {dur} | ⛽ {r.fuel_consumed:.1f} л\n"
            f"  👤 {r.stop_user_name or r.start_user_name or 'Оператор'}"
        )

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=get_reports_inline())
    await callback.answer()


@reports_router.callback_query(F.data == "report_fuel_last10")
async def cb_report_fuel_last10(callback: CallbackQuery):
    async with async_session_maker() as session:
        res = await session.execute(
            select(FuelLog).order_by(FuelLog.id.desc()).limit(10)
        )
        fuels = res.scalars().all()

    if not fuels:
        await callback.message.edit_text(
            "⛽ <b>Журнал заправок пуст</b>",
            parse_mode="HTML",
            reply_markup=get_reports_inline()
        )
        await callback.answer()
        return

    lines = ["⛽ <b>Последние заправки генератора:</b>\n"]
    for f in fuels:
        dt_str = format_dt(f.timestamp)
        note = f" ({f.notes})" if f.notes else ""
        lines.append(
            f"• <b>{dt_str}</b>: <code>+{f.amount_liters:.1f} л</code> → {f.fuel_after:.1f} л\n"
            f"  👤 {f.user_name or 'Оператор'}{note}"
        )

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=get_reports_inline())
    await callback.answer()


@reports_router.callback_query(F.data == "report_excel")
async def cb_report_excel(callback: CallbackQuery):
    await callback.answer("Генерирую Excel файл...")
    async with async_session_maker() as session:
        file_stream = await ExcelService.generate_full_report(session)

    filename = f"generator_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    input_file = BufferedInputFile(file_stream.getvalue(), filename=filename)

    await callback.message.answer_document(
        document=input_file,
        caption="📊 <b>Полный отчет по генератору (сводка, запуски, заправки, ТО)</b>",
        parse_mode="HTML"
    )
