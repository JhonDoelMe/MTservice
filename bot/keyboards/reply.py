from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_keyboard(is_running: bool = False, is_admin: bool = False) -> ReplyKeyboardMarkup:
    # Action button dynamically shows Start or Stop with prominent emoji
    if is_running:
        power_button = KeyboardButton(text="⏹️ Остановить генератор")
    else:
        power_button = KeyboardButton(text="▶️ Запустить генератор")

    keyboard = [
        [power_button, KeyboardButton(text="📊 Статус")],
        [KeyboardButton(text="⛽ Заправка"), KeyboardButton(text="🔧 ТО")],
        [KeyboardButton(text="📈 Отчеты")]
    ]

    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Настройки")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True
    )
