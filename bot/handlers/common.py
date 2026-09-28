from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from bot.config import settings
from bot.database.db import get_session_maker
from bot.services.generator_service import GeneratorService, format_dt, format_duration

common_router = Router()


def get_miniapp_keyboard() -> InlineKeyboardMarkup:
    webapp_url = settings.WEBAPP_URL or "http://localhost:8080"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Відкрити диспетчерську (Mini App)",
                    web_app=WebAppInfo(url=webapp_url)
                )
            ]
        ]
    )


@common_router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    session_maker = get_session_maker()
    async with session_maker() as session:
        dash = await GeneratorService.get_dashboard_data(session)

    status_badge = "🟢 <b>В РОБОТІ</b>" if dash["is_running"] else "🔴 <b>ЗУПИНЕНО</b>"

    text = (
        f"👋 Вітаємо, <b>{message.from_user.full_name}</b>!\n\n"
        f"⚙️ <b>Об'єкт:</b> {dash['name']}\n"
        f"⚡ <b>Поточний стан:</b> {status_badge}\n"
        f"⏱ <b>Напрацювання:</b> <code>{dash['total_hours']:.2f} мч</code>\n"
        f"⛽ <b>Залишок пального:</b> <code>{dash['current_fuel']:.1f} л</code> ({dash['fuel_pct']:.0f}%)\n"
        f"🔧 <b>До планового ТО:</b> <code>{dash['hours_to_maint']:.1f} мч</code>\n\n"
        f"🚀 <i>Управління генератором, журнал заправок, облік мотогодин та звіти доступні у Telegram Mini App.</i>\n\n"
        f"Натисніть кнопку нижче для запуску:"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_miniapp_keyboard()
    )


@common_router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 <b>Довідка диспетчерської генератора MTservice</b>\n\n"
        "Вся робота з генератором повністю здійснюється через <b>Telegram Mini App</b>:\n"
        "• <b>Запуск та зупинка</b> генератора з миттєвим або ретроспективним часом.\n"
        "• <b>Автоматичний розрахунок</b> витрати пального за нормою та списання з бака.\n"
        "• <b>Фіксація заправок</b> з розрахунком вартості у гривнях (₴).\n"
        "• <b>Контроль регламентного ТО</b> та фіксація сервісних робіт.\n"
        "• <b>Завантаження повного звіту Excel (.xlsx)</b>.\n"
        "• <b>Калібрування та налаштування</b> для адміністраторів.\n\n"
        "Щоб відкрити інтерфейс, натисніть кнопку внизу повідомлення або меню «📱 Додаток» у чаті."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_miniapp_keyboard())


@common_router.message()
async def default_message_handler(message: Message):
    await message.answer(
        "⚡ Для керування генератором скористайтеся Telegram Mini App:",
        reply_markup=get_miniapp_keyboard()
    )
