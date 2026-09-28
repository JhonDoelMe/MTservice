from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from bot.database.db import async_session_maker
from bot.database.models import MaintenanceLog
from bot.keyboards.inline import get_maintenance_inline, get_cancel_inline
from bot.services.generator_service import GeneratorService, format_dt

maintenance_router = Router()


class MaintenanceFSM(StatesGroup):
    waiting_for_description = State()
    waiting_for_replaced_parts = State()


@maintenance_router.message(F.text == "🔧 ТО")
async def msg_maintenance_menu(message: Message):
    async with async_session_maker() as session:
        dash = await GeneratorService.get_dashboard_data(session)

    hours_to_maint = dash["hours_to_maint"]
    if hours_to_maint <= 0:
        status_text = f"🔴 <b>ВНИМАНИЕ: ТО ПРОСРОЧЕНО на {abs(hours_to_maint):.1f} мч!</b>"
    elif hours_to_maint <= dash["warning_hours"]:
        status_text = f"🟡 <b>Внимание: приближается плановое ТО (осталось {hours_to_maint:.1f} мч)!</b>"
    else:
        status_text = f"🟢 <b>До планового ТО: {hours_to_maint:.1f} мч (норма)</b>"

    last_date_str = format_dt(dash["last_maintenance_date"], include_time=False)

    text = (
        f"🔧 <b>Техническое обслуживание (ТО)</b>\n"
        f"────────────────────\n"
        f"• Текущая наработка: <code>{dash['total_hours']:.2f} мч</code>\n"
        f"• Интервал обслуживания: <code>каждые {dash['maintenance_interval_hours']:.0f} мч</code>\n"
        f"• Предыдущее ТО: <code>{dash['last_maintenance_hours']:.1f} мч</code> ({last_date_str})\n"
        f"• Следующее ТО на отметке: <code>{(dash['last_maintenance_hours'] + dash['maintenance_interval_hours']):.1f} мч</code>\n\n"
        f"Статус: {status_text}\n"
        f"────────────────────"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_maintenance_inline())


@maintenance_router.callback_query(F.data == "maint_perform")
async def cb_maint_perform(callback: CallbackQuery, state: FSMContext):
    await state.set_state(MaintenanceFSM.waiting_for_description)
    text = (
        "🛠 <b>Фиксация проведения ТО</b>\n\n"
        "Опишите выполненные работы и замененные расходники\n"
        "(например: <i>«Замена моторного масла 15W-40, замена масляного и топливного фильтров, продувка воздушного»</i>):"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_cancel_inline())
    await callback.answer()


@maintenance_router.message(MaintenanceFSM.waiting_for_description)
async def process_maint_description(message: Message, state: FSMContext):
    desc = message.text.strip()
    if len(desc) < 3:
        await message.answer("Пожалуйста, укажите описание подробнее:", reply_markup=get_cancel_inline())
        return

    await state.clear()
    user = message.from_user

    async with async_session_maker() as session:
        ok, msg, res = await GeneratorService.perform_maintenance(
            session,
            user_id=user.id,
            user_name=user.full_name or user.username or "Оператор",
            description=desc
        )

    if not ok:
        await message.answer(f"❌ {msg}")
        return

    text = (
        f"✅ <b>Техническое обслуживание успешно зафиксировано!</b>\n\n"
        f"⏱ <b>Наработка на момент ТО:</b> <code>{res['hours_at_maint']:.2f} мч</code>\n"
        f"📅 <b>Следующее ТО запланировано на:</b> <code>{res['next_maint_hours']:.2f} мч</code> (через {res['interval']:.0f} мч)\n"
        f"📝 <b>Выполненные работы:</b> {res['description']}\n"
        f"👤 <b>Исполнитель:</b> {user.full_name}"
    )
    await message.answer(text, parse_mode="HTML")


@maintenance_router.callback_query(F.data == "maint_history")
async def cb_maint_history(callback: CallbackQuery):
    async with async_session_maker() as session:
        res = await session.execute(
            select(MaintenanceLog).order_by(MaintenanceLog.id.desc()).limit(5)
        )
        logs = res.scalars().all()

    if not logs:
        await callback.message.edit_text(
            "📋 <b>История ТО пуста</b>.\nПока еще не было зарегистрировано ни одного ТО.",
            parse_mode="HTML",
            reply_markup=get_maintenance_inline()
        )
        await callback.answer()
        return

    lines = ["📋 <b>Последние записи ТО:</b>\n"]
    for idx, l in enumerate(logs, start=1):
        dt_str = format_dt(l.timestamp)
        lines.append(
            f"<b>{idx}. {dt_str}</b> | <code>{l.hours_at_maintenance:.1f} мч</code>\n"
            f"• <i>{l.description}</i>\n"
            f"• Исполнитель: {l.user_name or '—'}\n"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=get_maintenance_inline()
    )
    await callback.answer()
