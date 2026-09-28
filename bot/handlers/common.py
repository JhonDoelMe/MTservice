from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from bot.database.db import async_session_maker
from bot.keyboards.inline import get_dashboard_inline
from bot.keyboards.reply import get_main_keyboard
from bot.services.generator_service import (
    GeneratorService,
    format_dt,
    format_duration,
)

common_router = Router()


def make_progress_bar(pct: float, length: int = 10) -> str:
    filled = int(round((pct / 100.0) * length))
    filled = max(0, min(length, filled))
    empty = length - filled
    return "🟩" * filled + "⬜" * empty


def render_dashboard_text(d: dict) -> str:
    # Generator power status
    if d["is_running"]:
        start_str = format_dt(d["current_start_time"])
        duration_str = format_duration(d["current_run_hours"])
        op = d["current_start_user_name"] or "Оператор"
        status_line = (
            f"⚡ <b>Статус:</b> 🟢 <b>В РАБОТЕ</b>\n"
            f"🕒 <b>Запущен:</b> {start_str} ({op})\n"
            f"⏱ <b>Текущее время работы:</b> {duration_str}"
        )
    else:
        status_line = "⚡ <b>Статус:</b> 🔴 <b>ОСТАНОВЛЕН</b>"

    # Maintenance warning level
    hours_to_maint = d["hours_to_maint"]
    if hours_to_maint <= 0:
        maint_badge = f"🔴 <b>ВНИМАНИЕ! ТО ПРОСРОЧЕНО на {abs(hours_to_maint):.1f} мч!</b>"
    elif hours_to_maint <= d["warning_hours"]:
        maint_badge = f"🟡 <b>Скоро ТО! Осталось {hours_to_maint:.1f} мч</b>"
    else:
        maint_badge = f"🟢 <b>В норме (осталось {hours_to_maint:.1f} мч)</b>"

    # Fuel bar
    bar = make_progress_bar(d["fuel_pct"])
    fuel_warn = ""
    if d["fuel_pct"] <= 15:
        fuel_warn = "\n⚠️ <b>Критический остаток топлива! Необходима заправка!</b>"

    text = (
        f"⚙️ <b>{d['name']}</b>\n"
        f"────────────────────\n"
        f"{status_line}\n\n"
        f"⏱ <b>Общая наработка:</b> <code>{d['total_hours']:.2f} мч</code>\n\n"
        f"⛽ <b>Уровень топлива:</b> {bar} <b>{d['fuel_pct']:.0f}%</b>\n"
        f"• Остаток в баке: <code>{d['current_fuel']:.1f} л</code> из {d['tank_capacity']:.0f} л\n"
        f"• Норма расхода: <code>{d['fuel_rate']:.1f} л/ч</code>\n"
        f"• Хватит примерно на: <code>~{d['remaining_runtime_hours']:.1f} ч</code> работы{fuel_warn}\n\n"
        f"🔧 <b>Техническое обслуживание:</b>\n"
        f"• До следующего ТО: {maint_badge}\n"
        f"• Интервал ТО: <code>каждые {d['maintenance_interval_hours']:.0f} мч</code>\n"
        f"• Предыдущее ТО на: <code>{d['last_maintenance_hours']:.1f} мч</code>\n"
        f"────────────────────"
    )
    return text


@common_router.message(CommandStart())
async def cmd_start(message: Message, is_admin: bool = False):
    async with async_session_maker() as session:
        dash_data = await GeneratorService.get_dashboard_data(session)

    text = (
        f"👋 Здравствуйте, <b>{message.from_user.full_name}</b>!\n\n"
        f"Добро пожаловать в систему мониторинга и учета генератора.\n\n"
        f"{render_dashboard_text(dash_data)}"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_main_keyboard(dash_data["is_running"], is_admin)
    )


@common_router.message(F.text.in_(["📊 Статус", "/status"]))
async def show_status(message: Message, is_admin: bool = False):
    async with async_session_maker() as session:
        dash_data = await GeneratorService.get_dashboard_data(session)

    text = render_dashboard_text(dash_data)
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_dashboard_inline(dash_data["is_running"])
    )


@common_router.callback_query(F.data == "dash_refresh")
async def cb_dash_refresh(callback: CallbackQuery):
    async with async_session_maker() as session:
        dash_data = await GeneratorService.get_dashboard_data(session)

    text = render_dashboard_text(dash_data)
    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_dashboard_inline(dash_data["is_running"])
        )
    except Exception:
        pass
    await callback.answer("Данные обновлены")


@common_router.callback_query(F.data == "cancel_action")
async def cb_cancel_action(callback: CallbackQuery, state=None):
    if state:
        await state.clear()
    await callback.message.edit_text("Действие отменено.")
    await callback.answer("Отменено")


@common_router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 <b>Справка по боту учета генератора</b>\n\n"
        "• <b>Запустить генератор</b> — фиксирует точное время старта и оператора.\n"
        "• <b>Остановить генератор</b> — фиксирует остановку, автоматически рассчитывает время работы, расход топлива по норме и списывает его из бака, увеличивает счетчик наработки.\n"
        "• <b>Статус</b> — показывает текущее состояние, остаток топлива, график работы и счетчик до ТО.\n"
        "• <b>Заправка</b> — внесение данных о залитом топливе для поддержания актуального уровня бака.\n"
        "• <b>ТО</b> — просмотр оставшихся моточасов и фиксация проведения регламентных работ.\n"
        "• <b>Отчеты</b> — статистика работы и выгрузка подробного Excel-файла со всеми логами."
    )
    await message.answer(text, parse_mode="HTML")
