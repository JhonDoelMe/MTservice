from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from bot.database.db import async_session_maker
from bot.database.models import User
from bot.keyboards.inline import get_admin_settings_inline, get_cancel_inline, get_user_approval_inline
from bot.keyboards.reply import get_main_keyboard
from bot.services.generator_service import GeneratorService

admin_router = Router()


class AdminFSM(StatesGroup):
    waiting_for_hours = State()
    waiting_for_fuel = State()
    waiting_for_rate = State()
    waiting_for_tank = State()
    waiting_for_interval = State()


@admin_router.message(F.text == "⚙️ Настройки")
async def msg_admin_settings(message: Message, is_admin: bool = False):
    if not is_admin:
        await message.answer("⛔ Доступ к настройкам разрешен только администраторам.")
        return

    async with async_session_maker() as session:
        gen = await GeneratorService.get_state(session)

    text = (
        "⚙️ <b>Панель управления администратора</b>\n\n"
        f"• Название: <b>{gen.name}</b>\n"
        f"• Счетчик моточасов: <code>{gen.total_hours:.2f} мч</code>\n"
        f"• Остаток топлива в баке: <code>{gen.current_fuel:.1f} л</code>\n"
        f"• Паспортный расход: <code>{gen.fuel_rate:.1f} л/ч</code>\n"
        f"• Объем бака: <code>{gen.tank_capacity:.0f} л</code>\n"
        f"• Интервал ТО: <code>{gen.maintenance_interval_hours:.0f} мч</code>\n\n"
        "Выберите параметр для корректировки:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_admin_settings_inline())


@admin_router.callback_query(F.data == "admin_calib_hours")
async def cb_calib_hours(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_for_hours)
    await callback.message.edit_text(
        "⏱ <b>Калибровка моточасов</b>\n\nВведите точное значение физического счетчика моточасов на генераторе (например: <code>145.5</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_inline()
    )
    await callback.answer()


@admin_router.message(AdminFSM.waiting_for_hours)
async def process_calib_hours(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    try:
        val = float(message.text.replace(",", ".").strip())
        if val < 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите неотрицательное число:", reply_markup=get_cancel_inline())
        return

    await state.clear()
    async with async_session_maker() as session:
        gen = await GeneratorService.calibrate_counters(session, total_hours=val)

    await message.answer(
        f"✅ Счетчик моточасов успешно установлен на <b>{gen.total_hours:.2f} мч</b>.",
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_calib_fuel")
async def cb_calib_fuel(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_for_fuel)
    await callback.message.edit_text(
        "⛽ <b>Калибровка остатка бака</b>\n\nВведите фактический объем топлива в баке в литрах (например: <code>85.0</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_inline()
    )
    await callback.answer()


@admin_router.message(AdminFSM.waiting_for_fuel)
async def process_calib_fuel(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    try:
        val = float(message.text.replace(",", ".").strip())
        if val < 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите положительное число:", reply_markup=get_cancel_inline())
        return

    await state.clear()
    async with async_session_maker() as session:
        gen = await GeneratorService.calibrate_counters(session, current_fuel=val)

    await message.answer(
        f"✅ Остаток топлива в баке скорректирован на <b>{gen.current_fuel:.1f} л</b>.",
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_set_fuel_rate")
async def cb_set_rate(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_for_rate)
    await callback.message.edit_text(
        "📉 <b>Изменение нормы расхода</b>\n\nВведите норму расхода топлива в литрах в час (например: <code>4.8</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_inline()
    )
    await callback.answer()


@admin_router.message(AdminFSM.waiting_for_rate)
async def process_set_rate(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    try:
        val = float(message.text.replace(",", ".").strip())
        if val <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите число больше 0:", reply_markup=get_cancel_inline())
        return

    await state.clear()
    async with async_session_maker() as session:
        gen = await GeneratorService.calibrate_counters(session, fuel_rate=val)

    await message.answer(
        f"✅ Норма расхода установлена: <b>{gen.fuel_rate:.2f} л/ч</b>.",
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_set_tank_cap")
async def cb_set_tank(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_for_tank)
    await callback.message.edit_text(
        "🛢 <b>Изменение объема бака</b>\n\nВведите паспортный объем бака генератора в литрах (например: <code>200</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_inline()
    )
    await callback.answer()


@admin_router.message(AdminFSM.waiting_for_tank)
async def process_set_tank(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    try:
        val = float(message.text.replace(",", ".").strip())
        if val <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите число больше 0:", reply_markup=get_cancel_inline())
        return

    await state.clear()
    async with async_session_maker() as session:
        gen = await GeneratorService.calibrate_counters(session, tank_capacity=val)

    await message.answer(
        f"✅ Объем бака установлен: <b>{gen.tank_capacity:.0f} л</b>.",
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "admin_set_maint_interval")
async def cb_set_maint_interval(callback: CallbackQuery, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return
    await state.set_state(AdminFSM.waiting_for_interval)
    await callback.message.edit_text(
        "🔧 <b>Интервал планового ТО</b>\n\nВведите интервал между ТО в моточасах (например: <code>250</code> или <code>100</code>):",
        parse_mode="HTML",
        reply_markup=get_cancel_inline()
    )
    await callback.answer()


@admin_router.message(AdminFSM.waiting_for_interval)
async def process_set_maint_interval(message: Message, state: FSMContext, is_admin: bool = False):
    if not is_admin:
        return
    try:
        val = float(message.text.replace(",", ".").strip())
        if val <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("❌ Введите число больше 0:", reply_markup=get_cancel_inline())
        return

    await state.clear()
    async with async_session_maker() as session:
        gen = await GeneratorService.calibrate_counters(session, maintenance_interval=val)

    await message.answer(
        f"✅ Интервал планового ТО установлен: <b>{gen.maintenance_interval_hours:.0f} мч</b>.",
        parse_mode="HTML"
    )


# --- USER MANAGEMENT ---

@admin_router.callback_query(F.data == "admin_users_list")
async def cb_admin_users_list(callback: CallbackQuery, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return

    async with async_session_maker() as session:
        res = await session.execute(select(User).order_by(User.created_at.desc()))
        users = res.scalars().all()

    lines = ["👥 <b>Пользователи системы:</b>\n"]
    for u in users:
        role_emoji = "👑" if u.role == "admin" else ("👤" if u.role == "operator" else ("⏳" if u.role == "pending" else "⛔"))
        username_str = f" (@{u.username})" if u.username else ""
        lines.append(f"{role_emoji} <b>{u.full_name}</b>{username_str} — <code>{u.role}</code> (ID: <code>{u.user_id}</code>)")

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=get_admin_settings_inline())
    await callback.answer()


@admin_router.callback_query(F.data.startswith("adm_appr_"))
async def cb_approve_user(callback: CallbackQuery, bot: Bot, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return

    target_id = int(callback.data.split("_")[-1])
    async with async_session_maker() as session:
        u = await session.get(User, target_id)
        if u:
            u.role = "operator"
            await session.commit()
            target_name = u.full_name
        else:
            target_name = str(target_id)

    await callback.message.edit_text(f"✅ Пользователю <b>{target_name}</b> (ID: <code>{target_id}</code>) выдана роль <b>Оператор</b>.", parse_mode="HTML")
    await callback.answer("Пользователь одобрен!")

    try:
        await bot.send_message(
            chat_id=target_id,
            text="🎉 <b>Доступ одобрен!</b>\nАдминистратор предоставил вам доступ к управлению генератором.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(is_running=False, is_admin=False)
        )
    except Exception:
        pass


@admin_router.callback_query(F.data.startswith("adm_make_"))
async def cb_make_admin_user(callback: CallbackQuery, bot: Bot, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return

    target_id = int(callback.data.split("_")[-1])
    async with async_session_maker() as session:
        u = await session.get(User, target_id)
        if u:
            u.role = "admin"
            await session.commit()
            target_name = u.full_name
        else:
            target_name = str(target_id)

    await callback.message.edit_text(f"👑 Пользователю <b>{target_name}</b> (ID: <code>{target_id}</code>) выдана роль <b>Администратор</b>.", parse_mode="HTML")
    await callback.answer("Сделан администратором!")

    try:
        await bot.send_message(
            chat_id=target_id,
            text="👑 <b>Вам выданы права Администратора!</b>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard(is_running=False, is_admin=True)
        )
    except Exception:
        pass


@admin_router.callback_query(F.data.startswith("adm_block_"))
async def cb_block_user(callback: CallbackQuery, bot: Bot, is_admin: bool = False):
    if not is_admin:
        await callback.answer("Только для администраторов", show_alert=True)
        return

    target_id = int(callback.data.split("_")[-1])
    async with async_session_maker() as session:
        u = await session.get(User, target_id)
        if u:
            u.role = "blocked"
            await session.commit()
            target_name = u.full_name
        else:
            target_name = str(target_id)

    await callback.message.edit_text(f"⛔ Пользователь <b>{target_name}</b> (ID: <code>{target_id}</code>) заблокирован.", parse_mode="HTML")
    await callback.answer("Пользователь заблокирован!")
