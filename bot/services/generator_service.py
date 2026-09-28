from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.config import settings
from bot.database.models import GeneratorState, RunLog, FuelLog, MaintenanceLog
from bot.database.cache import cache


def get_local_tz():
    try:
        return ZoneInfo(settings.TIMEZONE)
    except Exception:
        return timezone.utc


def utc_to_local(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(get_local_tz())


def format_dt(dt: Optional[datetime], include_time: bool = True) -> str:
    if dt is None:
        return "—"
    local_dt = utc_to_local(dt)
    if include_time:
        return local_dt.strftime("%d.%m.%Y %H:%M")
    return local_dt.strftime("%d.%m.%Y")


def format_duration(hours_float: float) -> str:
    total_minutes = int(round(hours_float * 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours > 0 and minutes > 0:
        return f"{hours} год {minutes} хв ({hours_float:.2f} год)"
    elif hours > 0:
        return f"{hours} год"
    else:
        return f"{minutes} хв ({hours_float:.2f} год)"


class GeneratorService:

    @staticmethod
    async def get_state(session: AsyncSession) -> GeneratorState:
        result = await session.execute(select(GeneratorState).where(GeneratorState.id == 1))
        gen = result.scalar_one_or_none()
        if not gen:
            gen = GeneratorState(
                id=1,
                name=settings.GENERATOR_NAME,
                is_running=False,
                total_hours=settings.INITIAL_TOTAL_HOURS,
                current_fuel=settings.INITIAL_FUEL_LEVEL,
                fuel_rate=settings.FUEL_RATE_PER_HOUR,
                tank_capacity=settings.TANK_CAPACITY,
                maintenance_interval_hours=settings.MAINTENANCE_INTERVAL_HOURS,
                last_maintenance_hours=settings.INITIAL_TOTAL_HOURS,
            )
            session.add(gen)
            await session.commit()
            await session.refresh(gen)
        return gen

    @staticmethod
    async def get_dashboard_data(session: AsyncSession) -> Dict[str, Any]:
        # Check cache first
        cached = await cache.get("generator:dashboard")
        if cached:
            return cached

        gen = await GeneratorService.get_state(session)
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        current_run_hours = 0.0
        current_fuel_estimate = gen.current_fuel
        total_hours_estimate = gen.total_hours

        session_fuel_burned = 0.0
        if gen.is_running and gen.current_start_time:
            delta = now_utc - gen.current_start_time
            current_run_hours = max(0.0, delta.total_seconds() / 3600.0)
            session_fuel_burned = round(current_run_hours * gen.fuel_rate, 2)
            current_fuel_estimate = max(0.0, gen.current_fuel - session_fuel_burned)
            total_hours_estimate = gen.total_hours + current_run_hours

        hours_to_maint = (gen.last_maintenance_hours + gen.maintenance_interval_hours) - total_hours_estimate

        fuel_pct = 0.0
        if gen.tank_capacity > 0:
            fuel_pct = min(100.0, max(0.0, (current_fuel_estimate / gen.tank_capacity) * 100))

        remaining_runtime_hours = 0.0
        if gen.fuel_rate > 0:
            remaining_runtime_hours = current_fuel_estimate / gen.fuel_rate

        # Get today's total fuel burned
        local_tz = get_local_tz()
        start_of_day_local = datetime.now(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_day_utc = start_of_day_local.astimezone(timezone.utc).replace(tzinfo=None)

        today_runs_res = await session.execute(
            select(RunLog).where(RunLog.stop_time >= start_of_day_utc)
        )
        today_runs = today_runs_res.scalars().all()
        today_runs_fuel = sum(r.fuel_consumed for r in today_runs)
        today_fuel_burned = round(today_runs_fuel + session_fuel_burned, 2)

        # Get last refuel
        last_fuel_res = await session.execute(
            select(FuelLog).order_by(FuelLog.id.desc()).limit(1)
        )
        last_fuel = last_fuel_res.scalar_one_or_none()
        last_refuel_data = None
        if last_fuel:
            last_refuel_data = {
                "amount_liters": round(last_fuel.amount_liters, 1),
                "cost": last_fuel.cost,
                "timestamp_formatted": format_dt(last_fuel.timestamp),
                "user_name": last_fuel.user_name,
                "notes": last_fuel.notes,
                "fuel_after": round(last_fuel.fuel_after, 1),
            }

        data = {
            "name": gen.name,
            "is_running": gen.is_running,
            "current_start_time": gen.current_start_time.isoformat() if gen.current_start_time else None,
            "current_start_time_formatted": format_dt(gen.current_start_time) if gen.current_start_time else None,
            "current_start_user_name": gen.current_start_user_name,
            "current_run_hours": round(current_run_hours, 2),
            "current_run_duration_str": format_duration(current_run_hours),
            "total_hours": round(total_hours_estimate, 2),
            "base_total_hours": round(gen.total_hours, 2),
            "current_fuel": round(current_fuel_estimate, 1),
            "fuel_rate": round(gen.fuel_rate, 2),
            "tank_capacity": round(gen.tank_capacity, 0),
            "fuel_pct": round(fuel_pct, 1),
            "remaining_runtime_hours": round(remaining_runtime_hours, 1),
            "session_fuel_burned": session_fuel_burned,
            "today_fuel_burned": today_fuel_burned,
            "last_refuel": last_refuel_data,
            "last_maintenance_hours": round(gen.last_maintenance_hours, 1),
            "last_maintenance_date": gen.last_maintenance_date.isoformat() if gen.last_maintenance_date else None,
            "last_maintenance_date_formatted": format_dt(gen.last_maintenance_date, include_time=False) if gen.last_maintenance_date else "—",
            "maintenance_interval_hours": round(gen.maintenance_interval_hours, 0),
            "hours_to_maint": round(hours_to_maint, 2),
            "warning_hours": settings.MAINTENANCE_WARNING_HOURS,
            "currency": settings.CURRENCY,
            "timezone": settings.TIMEZONE,
        }

        # Cache for 2 seconds during running, 10 seconds when stopped
        ttl = 2 if gen.is_running else 10
        await cache.set("generator:dashboard", data, ttl=ttl)
        return data

    @staticmethod
    async def start_generator(
        session: AsyncSession,
        user_id: int,
        user_name: str,
        custom_start_time: Optional[datetime] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        gen = await GeneratorService.get_state(session)
        if gen.is_running:
            start_str = format_dt(gen.current_start_time)
            return False, f"⚠️ Генератор вже запущено ({start_str}) оператором {gen.current_start_user_name or 'Невідомо'}!", None

        start_time = custom_start_time or datetime.now(timezone.utc).replace(tzinfo=None)

        if gen.current_fuel <= 0.5:
            return False, f"❌ Неможливо запустити генератор: критично мало пального ({gen.current_fuel:.1f} л)! Спочатку заправте генератор.", None

        gen.is_running = True
        gen.current_start_time = start_time
        gen.current_start_user_id = user_id
        gen.current_start_user_name = user_name
        gen.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await session.commit()
        await session.refresh(gen)
        await cache.delete("generator:dashboard")

        return True, "✅ Генератор успішно запущено!", {
            "start_time": start_time,
            "operator": user_name,
            "current_fuel": gen.current_fuel,
            "total_hours": gen.total_hours,
            "hours_to_maint": (gen.last_maintenance_hours + gen.maintenance_interval_hours) - gen.total_hours,
        }

    @staticmethod
    async def stop_generator(
        session: AsyncSession,
        user_id: int,
        user_name: str,
        custom_stop_time: Optional[datetime] = None,
        notes: Optional[str] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        gen = await GeneratorService.get_state(session)
        if not gen.is_running:
            return False, "⚠️ Генератор зараз не працює!", None

        stop_time = custom_stop_time or datetime.now(timezone.utc).replace(tzinfo=None)
        start_time = gen.current_start_time or stop_time

        if stop_time < start_time:
            return False, "❌ Час зупинки не може бути раніше часу запуску!", None

        delta = stop_time - start_time
        duration_hours = max(0.01, delta.total_seconds() / 3600.0)
        fuel_consumed = round(duration_hours * gen.fuel_rate, 2)
        start_fuel = gen.current_fuel
        end_fuel = round(max(0.0, start_fuel - fuel_consumed), 2)
        new_total_hours = round(gen.total_hours + duration_hours, 2)

        run_log = RunLog(
            start_time=start_time,
            stop_time=stop_time,
            duration_hours=round(duration_hours, 2),
            fuel_consumed=fuel_consumed,
            fuel_rate=gen.fuel_rate,
            start_fuel=start_fuel,
            end_fuel=end_fuel,
            total_hours_after=new_total_hours,
            start_user_id=gen.current_start_user_id,
            start_user_name=gen.current_start_user_name,
            stop_user_id=user_id,
            stop_user_name=user_name,
            notes=notes
        )
        session.add(run_log)

        gen.is_running = False
        gen.current_start_time = None
        gen.current_start_user_id = None
        gen.current_start_user_name = None
        gen.total_hours = new_total_hours
        gen.current_fuel = end_fuel
        gen.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        await session.commit()
        await session.refresh(gen)
        await cache.delete("generator:dashboard")

        hours_to_maint = (gen.last_maintenance_hours + gen.maintenance_interval_hours) - new_total_hours

        return True, "✅ Генератор успішно зупинено!", {
            "start_time": start_time,
            "stop_time": stop_time,
            "duration_hours": duration_hours,
            "fuel_consumed": fuel_consumed,
            "start_fuel": start_fuel,
            "end_fuel": end_fuel,
            "total_hours": new_total_hours,
            "hours_to_maint": hours_to_maint,
            "operator": user_name,
        }

    @staticmethod
    async def add_fuel(
        session: AsyncSession,
        user_id: int,
        user_name: str,
        amount_liters: float,
        cost: Optional[float] = None,
        notes: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        if amount_liters <= 0:
            return False, "❌ Об'єм заправки повинен бути більше 0!", {}

        gen = await GeneratorService.get_state(session)
        fuel_before = gen.current_fuel
        fuel_after = round(fuel_before + amount_liters, 2)

        gen.current_fuel = fuel_after
        gen.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        fuel_log = FuelLog(
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            amount_liters=amount_liters,
            fuel_before=fuel_before,
            fuel_after=fuel_after,
            cost=cost,
            user_id=user_id,
            user_name=user_name,
            notes=notes
        )
        session.add(fuel_log)
        await session.commit()
        await session.refresh(gen)
        await cache.delete("generator:dashboard")

        return True, "✅ Заправку успішно зафіксовано!", {
            "amount": amount_liters,
            "fuel_before": fuel_before,
            "fuel_after": fuel_after,
            "tank_capacity": gen.tank_capacity,
            "cost": cost,
            "notes": notes,
        }

    @staticmethod
    async def perform_maintenance(
        session: AsyncSession,
        user_id: int,
        user_name: str,
        description: str,
        parts_replaced: Optional[str] = None,
        cost: Optional[float] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        gen = await GeneratorService.get_state(session)

        hours_at_maint = gen.total_hours
        next_maint_hours = round(hours_at_maint + gen.maintenance_interval_hours, 2)

        gen.last_maintenance_hours = hours_at_maint
        gen.last_maintenance_date = datetime.now(timezone.utc).replace(tzinfo=None)
        gen.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        maint_log = MaintenanceLog(
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            hours_at_maintenance=hours_at_maint,
            next_maintenance_hours=next_maint_hours,
            user_id=user_id,
            user_name=user_name,
            description=description,
            parts_replaced=parts_replaced,
            cost=cost
        )
        session.add(maint_log)
        await session.commit()
        await session.refresh(gen)
        await cache.delete("generator:dashboard")

        return True, "✅ Проведення ТО успішно збережено!", {
            "hours_at_maint": hours_at_maint,
            "next_maint_hours": next_maint_hours,
            "interval": gen.maintenance_interval_hours,
            "description": description,
            "cost": cost,
        }

    @staticmethod
    async def calibrate_counters(
        session: AsyncSession,
        total_hours: Optional[float] = None,
        current_fuel: Optional[float] = None,
        fuel_rate: Optional[float] = None,
        tank_capacity: Optional[float] = None,
        maintenance_interval: Optional[float] = None,
        last_maint_hours: Optional[float] = None,
    ) -> GeneratorState:
        gen = await GeneratorService.get_state(session)
        if total_hours is not None:
            gen.total_hours = total_hours
        if current_fuel is not None:
            gen.current_fuel = current_fuel
        if fuel_rate is not None:
            gen.fuel_rate = fuel_rate
        if tank_capacity is not None:
            gen.tank_capacity = tank_capacity
        if maintenance_interval is not None:
            gen.maintenance_interval_hours = maintenance_interval
        if last_maint_hours is not None:
            gen.last_maintenance_hours = last_maint_hours

        gen.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        await session.refresh(gen)
        await cache.delete("generator:dashboard")
        return gen
