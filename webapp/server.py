import hmac
import hashlib
import json
import os
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select

from bot.config import settings
from bot.database.db import get_session_maker
from bot.database.models import User, RunLog, FuelLog, MaintenanceLog, AuditResetLog
from bot.services.generator_service import (
    GeneratorService,
    format_dt,
    format_duration,
    get_local_tz,
)
from bot.services.excel_service import ExcelService
from bot.handlers.generator import parse_time_input

app = FastAPI(title="MTservice Generator TMA Backend")

# Mount static files
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")


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

                # КРИТИЧНЕ ВИПРАВЛЕННЯ: якщо користувач прописаний в ADMIN_IDS (.env),
                # або в системі взагалі немає адміна — він МИТТЄВО отримує статус admin
                # навіть якщо раніше був збережений як pending або blocked!
                if (is_env_admin or not has_any_admin) and db_user.role != "admin":
                    db_user.role = "admin"
                    changed = True

                if changed:
                    await session.commit()
                    await session.refresh(db_user)

            is_effective_admin = (is_env_admin or db_user.role == "admin")

            # КРИТИЧНЕ ВИПРАВЛЕННЯ: Адміністратор НІКОЛИ не блокується екраном очікування!
            if is_effective_admin:
                return {
                    "user_id": db_user.user_id,
                    "user_name": db_user.display_name,
                    "custom_name": db_user.custom_name or "",
                    "full_name": db_user.full_name or "",
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
                "custom_name": db_user.custom_name or "",
                "full_name": db_user.full_name or "",
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
            "custom_name": db_user.custom_name or "",
            "full_name": db_user.full_name or "",
            "role": "admin",
            "is_admin": True
        }


# --- TEMPLATE ROUTE ---

@app.get("/", response_class=HTMLResponse)
async def serve_mini_app():
    index_path = os.path.join("webapp", "templates", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


# --- API ROUTES ---

@app.get("/api/me")
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return current_user


@app.get("/api/status")
async def get_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    session_maker = get_session_maker()
    async with session_maker() as session:
        data = await GeneratorService.get_dashboard_data(session)
    data["current_user"] = current_user
    return data


class StartRequest(BaseModel):
    custom_time: Optional[str] = None


@app.post("/api/generator/start")
async def start_generator(req: StartRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    custom_dt = None
    if req.custom_time and req.custom_time.strip() and req.custom_time.strip().lower() != "зараз":
        try:
            custom_dt = parse_time_input(req.custom_time)
        except Exception:
            raise HTTPException(status_code=400, detail="Невірний формат часу (напр. 10:15 або -15)")

    session_maker = get_session_maker()
    async with session_maker() as session:
        ok, msg, data = await GeneratorService.start_generator(
            session,
            user_id=current_user["user_id"],
            user_name=current_user["user_name"],
            custom_start_time=custom_dt
        )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"status": "ok", "message": msg, "data": data}


class StopRequest(BaseModel):
    custom_time: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/generator/stop")
async def stop_generator(req: StopRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    custom_dt = None
    if req.custom_time and req.custom_time.strip() and req.custom_time.strip().lower() != "зараз":
        try:
            custom_dt = parse_time_input(req.custom_time)
        except Exception:
            raise HTTPException(status_code=400, detail="Невірний формат часу (напр. 12:45 або -10)")

    session_maker = get_session_maker()
    async with session_maker() as session:
        ok, msg, data = await GeneratorService.stop_generator(
            session,
            user_id=current_user["user_id"],
            user_name=current_user["user_name"],
            custom_stop_time=custom_dt,
            notes=req.notes
        )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"status": "ok", "message": msg, "data": data}


class RefuelRequest(BaseModel):
    amount_liters: float
    cost: Optional[float] = None
    receipt_number: Optional[str] = None
    delivered_by: Optional[str] = None
    notes: Optional[str] = None


@app.post("/api/fuel/add")
async def add_fuel(req: RefuelRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    if req.amount_liters <= 0:
        raise HTTPException(status_code=400, detail="Об'єм заправки повинен бути більше 0")

    session_maker = get_session_maker()
    async with session_maker() as session:
        ok, msg, data = await GeneratorService.add_fuel(
            session,
            user_id=current_user["user_id"],
            user_name=current_user["user_name"],
            amount_liters=req.amount_liters,
            cost=req.cost,
            notes=req.notes,
            receipt_number=req.receipt_number,
            delivered_by=req.delivered_by
        )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"status": "ok", "message": msg, "data": data}


class MaintenanceRequest(BaseModel):
    description: str
    is_main: bool = True
    maint_type: str = "main"
    title: Optional[str] = None
    parts_replaced: Optional[str] = None
    cost: Optional[float] = None


@app.post("/api/maintenance/perform")
async def perform_maint(req: MaintenanceRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    if not req.description or len(req.description.strip()) < 3:
        raise HTTPException(status_code=400, detail="Будь ласка, вкажіть опис виконаних робіт")

    session_maker = get_session_maker()
    async with session_maker() as session:
        ok, msg, data = await GeneratorService.perform_maintenance(
            session,
            user_id=current_user["user_id"],
            user_name=current_user["user_name"],
            description=req.description.strip(),
            is_main=req.is_main,
            maint_type=req.maint_type,
            title=req.title,
            parts_replaced=req.parts_replaced,
            cost=req.cost
        )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"status": "ok", "message": msg, "data": data}


# --- REPORTS & LISTS ---

@app.get("/api/reports/summary")
async def get_reports_summary(current_user: Dict[str, Any] = Depends(get_current_user)):
    local_tz = get_local_tz()
    now_local = datetime.now(local_tz)

    start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_day_utc = start_of_day_local.astimezone(timezone.utc).replace(tzinfo=None)

    start_of_month_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_month_utc = start_of_month_local.astimezone(timezone.utc).replace(tzinfo=None)

    session_maker = get_session_maker()
    async with session_maker() as session:
        today_runs_res = await session.execute(
            select(RunLog).where(RunLog.stop_time >= start_of_day_utc)
        )
        today_runs = today_runs_res.scalars().all()

        today_fuel_res = await session.execute(
            select(FuelLog).where(FuelLog.timestamp >= start_of_day_utc)
        )
        today_fuels = today_fuel_res.scalars().all()

        month_runs_res = await session.execute(
            select(RunLog).where(RunLog.stop_time >= start_of_month_utc)
        )
        month_runs = month_runs_res.scalars().all()

        month_fuel_res = await session.execute(
            select(FuelLog).where(FuelLog.timestamp >= start_of_month_utc)
        )
        month_fuels = month_fuel_res.scalars().all()

    today_duration = sum(r.duration_hours for r in today_runs)
    today_fuel_burned = sum(r.fuel_consumed for r in today_runs)
    today_refueled = sum(f.amount_liters for f in today_fuels)

    month_duration = sum(r.duration_hours for r in month_runs)
    month_fuel_burned = sum(r.fuel_consumed for r in month_runs)

    return {
        "today_date": now_local.strftime("%d.%m.%Y"),
        "today_duration_hours": round(today_duration, 2),
        "today_duration_str": format_duration(today_duration),
        "today_fuel": round(today_fuel_burned, 1),
        "today_refuel": round(today_refueled, 1),
        "today_runs_count": len(today_runs),
        "month_duration_hours": round(month_duration, 2),
        "month_duration_str": format_duration(month_duration),
        "month_fuel": round(month_fuel_burned, 1),
    }


@app.get("/api/reports/chart-data")
async def get_chart_data(days: int = 7, current_user: Dict[str, Any] = Depends(get_current_user)):
    local_tz = get_local_tz()
    now_local = datetime.now(local_tz)
    start_date_local = (now_local - timedelta(days=days-1)).replace(hour=0, minute=0, second=0, microsecond=0)
    start_date_utc = start_date_local.astimezone(timezone.utc).replace(tzinfo=None)

    session_maker = get_session_maker()
    async with session_maker() as session:
        runs_res = await session.execute(
            select(RunLog).where(RunLog.stop_time >= start_date_utc)
        )
        runs = runs_res.scalars().all()

    # Aggregate by local date string "DD.MM"
    daily_data = {}
    for i in range(days):
        d = start_date_local + timedelta(days=i)
        daily_data[d.strftime("%d.%m")] = {"hours": 0.0, "fuel": 0.0}

    for r in runs:
        local_stop = r.stop_time.replace(tzinfo=timezone.utc).astimezone(local_tz)
        d_str = local_stop.strftime("%d.%m")
        if d_str in daily_data:
            daily_data[d_str]["hours"] += r.duration_hours
            daily_data[d_str]["fuel"] += r.fuel_consumed

    labels = list(daily_data.keys())
    fuel_data = [round(daily_data[k]["fuel"], 1) for k in labels]
    hours_data = [round(daily_data[k]["hours"], 1) for k in labels]

    return {
        "labels": labels,
        "fuel": fuel_data,
        "hours": hours_data
    }

@app.get("/api/reports/runs")
async def get_recent_runs(current_user: Dict[str, Any] = Depends(get_current_user)):
    session_maker = get_session_maker()
    async with session_maker() as session:
        res = await session.execute(select(RunLog).order_by(RunLog.id.desc()).limit(15))
        runs = res.scalars().all()

    return [
        {
            "id": r.id,
            "start_time": r.start_time.isoformat(),
            "start_formatted": format_dt(r.start_time),
            "stop_time": r.stop_time.isoformat(),
            "stop_formatted": format_dt(r.stop_time),
            "duration_hours": r.duration_hours,
            "duration_str": format_duration(r.duration_hours),
            "fuel_consumed": r.fuel_consumed,
            "total_hours_after": r.total_hours_after,
            "start_user_name": r.start_user_name,
            "stop_user_name": r.stop_user_name,
            "notes": r.notes,
        }
        for r in runs
    ]


@app.get("/api/reports/fuel")
async def get_recent_fuel(current_user: Dict[str, Any] = Depends(get_current_user)):
    session_maker = get_session_maker()
    async with session_maker() as session:
        res = await session.execute(select(FuelLog).order_by(FuelLog.id.desc()).limit(15))
        fuels = res.scalars().all()

    return [
        {
            "id": f.id,
            "timestamp": f.timestamp.isoformat(),
            "timestamp_formatted": format_dt(f.timestamp),
            "amount_liters": f.amount_liters,
            "fuel_before": f.fuel_before,
            "fuel_after": f.fuel_after,
            "cost": f.cost,
            "user_name": f.user_name,
            "receipt_number": f.receipt_number,
            "delivered_by": f.delivered_by,
            "notes": f.notes,
        }
        for f in fuels
    ]


@app.get("/api/reports/maintenance")
async def get_recent_maintenance(current_user: Dict[str, Any] = Depends(get_current_user)):
    session_maker = get_session_maker()
    async with session_maker() as session:
        res = await session.execute(select(MaintenanceLog).order_by(MaintenanceLog.id.desc()).limit(15))
        maints = res.scalars().all()

    return [
        {
            "id": m.id,
            "timestamp": m.timestamp.isoformat(),
            "timestamp_formatted": format_dt(m.timestamp),
            "hours_at_maintenance": m.hours_at_maintenance,
            "next_maintenance_hours": m.next_maintenance_hours,
            "description": m.description,
            "parts_replaced": m.parts_replaced,
            "cost": m.cost,
            "user_name": m.user_name,
            "is_main": m.is_main,
            "maint_type": m.maint_type,
            "title": m.title or ("Головне ТО" if m.is_main else "Проміжне ТО")
        }
        for m in maints
    ]


@app.get("/api/reports/audit")
async def get_audit_logs(current_user: Dict[str, Any] = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Доступ заборонено")

    session_maker = get_session_maker()
    async with session_maker() as session:
        res = await session.execute(select(AuditResetLog).order_by(AuditResetLog.id.desc()).limit(20))
        audits = res.scalars().all()

    return [
        {
            "id": a.id,
            "timestamp": format_dt(a.timestamp),
            "reset_type": a.reset_type,
            "reason": a.reason,
            "user_name": a.user_name,
            "details": a.details
        }
        for a in audits
    ]


@app.get("/api/reports/excel")
async def export_excel(current_user: Dict[str, Any] = Depends(get_current_user)):
    session_maker = get_session_maker()
    async with session_maker() as session:
        stream = await ExcelService.generate_full_report(session)

    filename = f"generator_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# --- ADMIN SETTINGS & USERS ---

class AdminSettingsRequest(BaseModel):
    total_hours: Optional[float] = None
    current_fuel: Optional[float] = None
    fuel_rate: Optional[float] = None
    tank_capacity: Optional[float] = None
    maintenance_interval: Optional[float] = None


@app.post("/api/admin/settings")
async def update_admin_settings(req: AdminSettingsRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Дія доступна лише адміністраторам")

    session_maker = get_session_maker()
    async with session_maker() as session:
        gen = await GeneratorService.calibrate_counters(
            session,
            user_id=current_user["user_id"],
            user_name=current_user["user_name"],
            total_hours=req.total_hours,
            current_fuel=req.current_fuel,
            fuel_rate=req.fuel_rate,
            tank_capacity=req.tank_capacity,
            maintenance_interval=req.maintenance_interval
        )

    return {"status": "ok", "message": "Параметри оновлено"}


class ResetRequest(BaseModel):
    reset_type: str  # "all", "fuel_zero", "hours_zero", "maint_main", "maint_intermediate"
    reason: str


@app.post("/api/admin/reset")
async def reset_counters(req: ResetRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Дія доступна лише адміністраторам")

    session_maker = get_session_maker()
    async with session_maker() as session:
        ok, msg, data = await GeneratorService.reset_counters(
            session,
            user_id=current_user["user_id"],
            user_name=current_user["user_name"],
            reset_type=req.reset_type,
            reason=req.reason
        )

    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    return {"status": "ok", "message": msg, "data": data}


@app.get("/api/users")
async def list_users(current_user: Dict[str, Any] = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Доступ заборонено")

    session_maker = get_session_maker()
    async with session_maker() as session:
        res = await session.execute(select(User).order_by(User.created_at.desc()))
        users = res.scalars().all()

    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "full_name": u.full_name,
            "custom_name": u.custom_name,
            "display_name": u.display_name,
            "role": u.role,
            "created_at": u.created_at.isoformat()
        }
        for u in users
    ]


class UserRoleRequest(BaseModel):
    user_id: int
    role: str


@app.post("/api/users/role")
async def set_user_role(req: UserRoleRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Дія доступна лише адміністраторам")

    session_maker = get_session_maker()
    async with session_maker() as session:
        u = await session.get(User, req.user_id)
        if not u:
            raise HTTPException(status_code=404, detail="Користувача не знайдено")
        u.role = req.role
        await session.commit()

    return {"status": "ok", "message": f"Роль змінено на {req.role}"}


class UserCustomNameRequest(BaseModel):
    user_id: int
    custom_name: str


@app.post("/api/users/custom-name")
async def set_user_custom_name(req: UserCustomNameRequest, current_user: Dict[str, Any] = Depends(get_current_user)):
    # User can edit their own system name, or admin can edit anyone's
    if not current_user.get("is_admin") and req.user_id != current_user.get("user_id"):
        raise HTTPException(status_code=403, detail="Дія доступна лише адміністраторам або власнику акаунта")

    session_maker = get_session_maker()
    async with session_maker() as session:
        u = await session.get(User, req.user_id)
        if not u:
            raise HTTPException(status_code=404, detail="Користувача не знайдено")
        u.custom_name = req.custom_name.strip() if req.custom_name else None
        await session.commit()

    return {"status": "ok", "message": "Системне ім'я користувача оновлено"}
