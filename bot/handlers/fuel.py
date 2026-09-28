from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from bot.database.db import async_session_maker
from bot.keyboards.inline import get_cancel_inline
from bot.services.generator_service import GeneratorService

fuel_router = Router()


class FuelFSM(StatesGroup):
    waiting_for_amount = State()
    waiting_for_comment = State()


@fuel_router.message(F.text == "⛽ Заправка")
async def msg_refuel_start(message: Message, state: FSMContext):
    async with async_session_maker() as session:
        gen = await GeneratorService.get_state(session)

    free_space = max(0.0, gen.tank_capacity - gen.current_fuel)

    text = (
        f"⛽ <b>Фиксация заправки генератора</b>\n\n"
        f"• Текущий остаток: <code>{gen.current_fuel:.1f} л</code>\n"
        f"• Емкость бака: <code>{gen.tank_capacity:.0f} л</code>\n"
        f"• Свободно до полного бака: <code>~{free_space:.1f} л</code>\n\n"
        f"Введите количество залитых литров (например: <code>50</code> или <code>65.5</code>):"
    )
    await state.set_state(FuelFSM.waiting_for_amount)
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_inline())


@fuel_router.callback_query(F.data == "fuel_add_start")
async def cb_refuel_start(callback: CallbackQuery, state: FSMContext):
    async with async_session_maker() as session:
        gen = await GeneratorService.get_state(session)

    free_space = max(0.0, gen.tank_capacity - gen.current_fuel)

    text = (
        f"⛽ <b>Фиксация заправки генератора</b>\n\n"
        f"• Текущий остаток: <code>{gen.current_fuel:.1f} л</code>\n"
        f"• Емкость бака: <code>{gen.tank_capacity:.0f} л</code>\n"
        f"• Свободно до полного бака: <code>~{free_space:.1f} л</code>\n\n"
        f"Введите количество залитых литров (например: <code>50</code> или <code>65.5</code>):"
    )
    await state.set_state(FuelFSM.waiting_for_amount)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_cancel_inline())
    await callback.answer()


@fuel_router.message(FuelFSM.waiting_for_amount)
async def process_fuel_amount(message: Message, state: FSMContext):
    text = message.text.replace(",", ".").strip()
    try:
        liters = float(text)
        if liters <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите положительное число литров (например: <code>40</code>):",
            parse_mode="HTML",
            reply_markup=get_cancel_inline()
        )
        return

    await state.update_data(liters=liters)
    await state.set_state(FuelFSM.waiting_for_comment)

    prompt = (
        f"Залито: <b>{liters:.1f} л</b>.\n\n"
        "Отправьте комментарий (например: <i>«АЗС Газпром, чек №41»</i> или <i>«Из резервной бочки»</i>),\n"
        "либо отправьте <code>-</code> (прочерк), если комментарий не требуется:"
    )
    await message.answer(prompt, parse_mode="HTML", reply_markup=get_cancel_inline())


@fuel_router.message(FuelFSM.waiting_for_comment)
async def process_fuel_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    liters = data["liters"]

    comment = message.text.strip()
    notes = None if comment in ["-", "—", "нет", "отсутствует"] else comment

    await state.clear()
    user = message.from_user

    async with async_session_maker() as session:
        ok, msg, res = await GeneratorService.add_fuel(
            session,
            user_id=user.id,
            user_name=user.full_name or user.username or "Оператор",
            amount_liters=liters,
            notes=notes
        )

    if not ok:
        await message.answer(f"❌ {msg}")
        return

    warning = ""
    if res["fuel_after"] > res["tank_capacity"]:
        warning = f"\n⚠️ <i>Внимание: расчетный объем ({res['fuel_after']:.1f} л) превышает паспортную емкость бака ({res['tank_capacity']:.0f} л)!</i>"

    summary = (
        f"✅ <b>Заправка успешно зафиксирована!</b>\n\n"
        f"⛽ <b>Залито:</b> <code>+{res['amount']:.1f} л</code>\n"
        f"📊 <b>Было в баке:</b> <code>{res['fuel_before']:.1f} л</code>\n"
        f"📈 <b>Стало в баке:</b> <code>{res['fuel_after']:.1f} л</code> из {res['tank_capacity']:.0f} л\n"
        f"👤 <b>Кто заправил:</b> {user.full_name}\n"
    )
    if notes:
        summary += f"📝 <b>Заметка:</b> {notes}\n"
    summary += warning

    await message.answer(summary, parse_mode="HTML")
