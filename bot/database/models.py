from datetime import datetime
from typing import Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GeneratorState(Base):
    __tablename__ = "generator_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(100), default="Основний ДГУ")
    is_running: Mapped[bool] = mapped_column(Boolean, default=False)
    current_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_start_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    current_start_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    total_hours: Mapped[float] = mapped_column(Float, default=0.0)
    current_fuel: Mapped[float] = mapped_column(Float, default=100.0)
    fuel_rate: Mapped[float] = mapped_column(Float, default=4.5)  # л / год
    tank_capacity: Mapped[float] = mapped_column(Float, default=150.0)  # л
    fuel_type: Mapped[str] = mapped_column(String(50), default="ДП")
    fuel_price: Mapped[float] = mapped_column(Float, default=52.40)
    auto_update_price: Mapped[bool] = mapped_column(Boolean, default=True)

    # Головне ТО (Заміна моторної оливи)
    maintenance_interval_hours: Mapped[float] = mapped_column(Float, default=250.0)
    last_maintenance_hours: Mapped[float] = mapped_column(Float, default=0.0)
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Проміжні ТО (лічильники останніх замін компонентів на мотогодинах)
    last_spark_plugs_hours: Mapped[float] = mapped_column(Float, default=0.0)
    last_air_filter_hours: Mapped[float] = mapped_column(Float, default=0.0)
    last_fuel_filter_hours: Mapped[float] = mapped_column(Float, default=0.0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    stop_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_hours: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_consumed: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_rate: Mapped[float] = mapped_column(Float, nullable=False)
    start_fuel: Mapped[float] = mapped_column(Float, nullable=False)
    end_fuel: Mapped[float] = mapped_column(Float, nullable=False)
    total_hours_after: Mapped[float] = mapped_column(Float, nullable=False)

    start_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    start_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    stop_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    stop_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FuelLog(Base):
    __tablename__ = "fuel_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    amount_liters: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_before: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_after: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    receipt_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Номер чеку / накладної
    delivered_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Хто привіз / водій (прізвище)


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    hours_at_maintenance: Mapped[float] = mapped_column(Float, nullable=False)
    next_maintenance_hours: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parts_replaced: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Головне ТО vs Проміжне ТО
    is_main: Mapped[bool] = mapped_column(Boolean, default=True)  # True = головне (олива), False = проміжне
    maint_type: Mapped[str] = mapped_column(String(100), default="main")  # main, spark_plugs, air_filter, fuel_filter, other
    title: Mapped[str] = mapped_column(String(255), default="Головне ТО (Заміна оливи)")


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    custom_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Ім'я в системі для зрозумілого логування
    role: Mapped[str] = mapped_column(String(32), default="pending")  # "admin", "operator", "pending", "blocked"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def display_name(self) -> str:
        if self.custom_name and self.custom_name.strip():
            return self.custom_name.strip()
        if self.full_name and self.full_name.strip():
            return self.full_name.strip()
        if self.username and self.username.strip():
            return f"@{self.username.strip()}"
        return f"ID:{self.user_id}"


class AuditResetLog(Base):
    __tablename__ = "audit_reset_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    reset_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "all", "fuel_zero", "hours_zero", "maint_main", "maint_intermediate"
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class InventoryItem(Base):
    __tablename__ = 'inventory_items'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(50), default='HB')
    min_threshold: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
