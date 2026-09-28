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
    name: Mapped[str] = mapped_column(String(100), default="Основной ДГУ")
    is_running: Mapped[bool] = mapped_column(Boolean, default=False)
    current_start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_start_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    current_start_user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    total_hours: Mapped[float] = mapped_column(Float, default=0.0)
    current_fuel: Mapped[float] = mapped_column(Float, default=100.0)
    fuel_rate: Mapped[float] = mapped_column(Float, default=4.5)  # л / ч
    tank_capacity: Mapped[float] = mapped_column(Float, default=150.0)  # л

    maintenance_interval_hours: Mapped[float] = mapped_column(Float, default=250.0)  # интервал ТО
    last_maintenance_hours: Mapped[float] = mapped_column(Float, default=0.0)
    last_maintenance_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    amount_liters: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_before: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_after: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MaintenanceLog(Base):
    __tablename__ = "maintenance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    hours_at_maintenance: Mapped[float] = mapped_column(Float, nullable=False)
    next_maintenance_hours: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    user_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    parts_replaced: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(32), default="operator")  # "admin", "operator", "pending", "blocked"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
