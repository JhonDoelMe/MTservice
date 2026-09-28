from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy import select
from bot.config import settings
from bot.database.db import async_session_maker
from bot.database.models import User
from bot.keyboards.inline import get_user_approval_inline


class AuthMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        telegram_user = data.get("event_from_user")
        if not telegram_user or telegram_user.is_bot:
            return await handler(event, data)

        user_id = telegram_user.id
        username = telegram_user.username
        full_name = telegram_user.full_name or "Без имени"

        async with async_session_maker() as session:
            # Check if user is configured as admin in settings
            is_env_admin = user_id in settings.ADMIN_IDS

            result = await session.execute(select(User).where(User.user_id == user_id))
            db_user = result.scalar_one_or_none()

            # Check if this is the very first user and no admins in env
            total_users_res = await session.execute(select(User))
            all_users = total_users_res.scalars().all()
            has_any_admin = any(u.role == "admin" for u in all_users) or len(settings.ADMIN_IDS) > 0

            if not db_user:
                # If no admins configured anywhere, make the first user admin
                if not has_any_admin or is_env_admin:
                    initial_role = "admin"
                else:
                    initial_role = "pending"

                db_user = User(
                    user_id=user_id,
                    username=username,
                    full_name=full_name,
                    role=initial_role
                )
                session.add(db_user)
                await session.commit()
                await session.refresh(db_user)

                if initial_role == "pending":
                    # Notify bot admins
                    bot = data.get("bot")
                    if bot:
                        admin_ids_to_notify = set(settings.ADMIN_IDS)
                        for u in all_users:
                            if u.role == "admin":
                                admin_ids_to_notify.add(u.user_id)

                        for adm_id in admin_ids_to_notify:
                            try:
                                await bot.send_message(
                                    chat_id=adm_id,
                                    text=(
                                        f"🔔 <b>Новый запрос доступа!</b>\n\n"
                                        f"👤 <b>Пользователь:</b> {full_name}\n"
                                        f"🔗 <b>Username:</b> @{username if username else 'отсутствует'}\n"
                                        f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
                                        f"Выберите действие для выдачи прав:"
                                    ),
                                    parse_mode="HTML",
                                    reply_markup=get_user_approval_inline(user_id)
                                )
                            except Exception:
                                pass
            else:
                # Update info if changed
                if is_env_admin and db_user.role != "admin":
                    db_user.role = "admin"
                    await session.commit()

            # Store user status in data context
            data["user_role"] = db_user.role
            data["is_admin"] = (db_user.role == "admin")

            # Check permissions
            if db_user.role == "blocked":
                text = "⛔ <b>Доступ запрещен.</b>\nВаш аккаунт заблокирован администратором системы."
                if isinstance(event, Message):
                    await event.answer(text, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer("Доступ запрещен!", show_alert=True)
                return

            if db_user.role == "pending":
                text = (
                    f"⏳ <b>Запрос на доступ отправлен.</b>\n\n"
                    f"Ваш ID: <code>{user_id}</code>\n"
                    f"Пожалуйста, обратитесь к администратору для подтверждения роли оператора."
                )
                if isinstance(event, Message):
                    await event.answer(text, parse_mode="HTML")
                elif isinstance(event, CallbackQuery):
                    await event.answer("Ожидайте подтверждения доступа администратором.", show_alert=True)
                return

        return await handler(event, data)
