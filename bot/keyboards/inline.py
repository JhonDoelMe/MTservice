from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_dashboard_inline(is_running: bool) -> InlineKeyboardMarkup:
    if is_running:
        action_btn = InlineKeyboardButton(text="⏹️ Остановить", callback_data="gen_stop_confirm")
    else:
        action_btn = InlineKeyboardButton(text="▶️ Запустить", callback_data="gen_start_confirm")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [action_btn, InlineKeyboardButton(text="🔄 Обновить", callback_data="dash_refresh")],
            [
                InlineKeyboardButton(text="⛽ Быстрая заправка", callback_data="fuel_add_start"),
                InlineKeyboardButton(text="📥 Excel отчет", callback_data="report_excel")
            ]
        ]
    )


def get_confirm_start_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, запустить сейчас", callback_data="gen_start_now"),
            ],
            [
                InlineKeyboardButton(text="🕒 Указать время старта", callback_data="gen_start_custom"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
            ]
        ]
    )


def get_confirm_stop_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏹️ Да, остановить сейчас", callback_data="gen_stop_now"),
            ],
            [
                InlineKeyboardButton(text="🕒 Указать время остановки", callback_data="gen_stop_custom"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
            ]
        ]
    )


def get_cancel_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")]
        ]
    )


def get_maintenance_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Зафиксировать выполнение ТО", callback_data="maint_perform")],
            [InlineKeyboardButton(text="📋 История ТО", callback_data="maint_history")],
            [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="dash_refresh")]
        ]
    )


def get_reports_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Сводка за сегодня", callback_data="report_today"),
                InlineKeyboardButton(text="📅 За текущий месяц", callback_data="report_month")
            ],
            [
                InlineKeyboardButton(text="📜 Последние 10 запусков", callback_data="report_runs_last10"),
                InlineKeyboardButton(text="⛽ Последние заправки", callback_data="report_fuel_last10")
            ],
            [
                InlineKeyboardButton(text="📥 Выгрузить полный отчет (.xlsx)", callback_data="report_excel")
            ]
        ]
    )


def get_admin_settings_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏱ Скорректировать моточасы", callback_data="admin_calib_hours")],
            [InlineKeyboardButton(text="⛽ Скорректировать остаток бака", callback_data="admin_calib_fuel")],
            [InlineKeyboardButton(text="📉 Изменить норму расхода (л/ч)", callback_data="admin_set_fuel_rate")],
            [InlineKeyboardButton(text="🛢 Изменить объем бака (л)", callback_data="admin_set_tank_cap")],
            [InlineKeyboardButton(text="🔧 Изменить интервал ТО (мч)", callback_data="admin_set_maint_interval")],
            [InlineKeyboardButton(text="👥 Управление доступом", callback_data="admin_users_list")],
        ]
    )


def get_user_approval_inline(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Схвалити (Оператор)", callback_data=f"adm_appr_{user_id}"),
                InlineKeyboardButton(text="👑 Зробити адміном", callback_data=f"adm_make_{user_id}")
            ],
            [
                InlineKeyboardButton(text="⛔ Заблокувати", callback_data=f"adm_block_{user_id}")
            ]
        ]
    )
