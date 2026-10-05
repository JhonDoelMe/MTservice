import hmac
import hashlib
import json
import urllib.parse
from typing import Optional, Dict, Any

from fastapi import HTTPException, Header
from sqlalchemy import select

from bot.config import settings
from bot.database.db import get_session_maker
from bot.database.models import User


def validate_telegram_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """Validates Telegram WebApp initData HMAC-SHA256 signature."""
    if not init_data:
        return None

    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

        secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if computed_hash == received_hash:
            user_data = json.loads(parsed_data.get("user", "{}"))
            return user_data
    except Exception:
        pass
    return None


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """Authenticates Telegram user with strict admin approval verification."""
    tg_user = validate_telegram_init_data(x_telegram_init_data) if x_telegram_init_data else None

    session_maker = get_session_maker()
    async with session_maker() as session:
        if tg_user and "id" in tg_user:
            try:
                user_id = int(tg_user["id"])
            except (ValueError, TypeError):
                user_id = tg_user["id"]

            username = tg_user.get("username")
            user_name = f"{tg_user.get('first_name', '')} {tg_user.get('last_name', '')}".strip() or username or "Оператор"

            # 1. Перевірка, чи вказаний користувач в .env (ADMIN_IDS) за ID або username
            is_env_admin = settings.is_admin(user_id, username)

            # 2. Перевірка, чи є в системі взагалі хоч один адміністратор
            total_users_res = await session.execute(select(User))
            all_users = total_users_res.scalars().all()
            has_any_admin = any(u.role == "admin" for u in all_users) or len(settings.ADMIN_IDS) > 0

            db_user = await session.get(User, user_id)
            if not db_user:
                # Перший користувач або користувач з .env автоматично стає admin
                initial_role = "admin" if (is_env_admin or not has_any_admin) else "pending"
                db_user = User(
                    user_id=user_id,
                    username=username,
                    full_name=user_name,
                    role=initial_role
                )
                session.add(db_user)
                await session.commit()
                await session.refresh(db_user)
            else:
                changed = False
                # Оновлення username/імені з Telegram за потреби
                if username and db_user.username != username:
                    db_user.username = username
                    changed = True
                if user_name and db_user.full_name != user_name and not db_user.custom_name:
                    db_user.full_name = user_name
                    changed = True

                # Якщо користувач прописаний в ADMIN_IDS (.env),
                # або в системі взагалі немає адміна — він отримує статус admin
                if (is_env_admin or not has_any_admin) and db_user.role != "admin":
                    db_user.role = "admin"
                    changed = True

                if changed:
                    await session.commit()
                    await session.refresh(db_user)

            is_effective_admin = (is_env_admin or db_user.role == "admin")

            # Адміністратор ніколи не блокується екраном очікування
            if is_effective_admin:
                return {
                    "user_id": db_user.user_id,
                    "user_name": db_user.display_name,
                    "role": "admin",
                    "is_admin": True
                }

            # Перевірка схвалення для звичайних користувачів
            if db_user.role == "pending":
                raise HTTPException(
                    status_code=403,
                    detail=f"⏳ Ваш акаунт (ID: {user_id}) очікує підтвердження адміністратором. Зверніться до керівника для надання доступу."
                )
            if db_user.role == "blocked":
                raise HTTPException(
                    status_code=403,
                    detail="⛔ Доступ до системи заблоковано адміністратором."
                )

            return {
                "user_id": db_user.user_id,
                "user_name": db_user.display_name,
                "role": db_user.role,
                "is_admin": False
            }

        # Dev fallback для локального тестування у браузері без Telegram
        int_admin_ids = [x for x in settings.ADMIN_IDS if isinstance(x, int)]
        default_admin_id = int_admin_ids[0] if int_admin_ids else 100000001

        db_user = await session.get(User, default_admin_id)
        if not db_user:
            db_user = User(
                user_id=default_admin_id,
                username="DevAdmin",
                full_name="Диспетчер",
                role="admin"
            )
            session.add(db_user)
            await session.commit()
            await session.refresh(db_user)
        elif db_user.role != "admin":
            db_user.role = "admin"
            await session.commit()
            await session.refresh(db_user)

        return {
            "user_id": db_user.user_id,
            "user_name": db_user.display_name,
            "role": "admin",
            "is_admin": True
        }
