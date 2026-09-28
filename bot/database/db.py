import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from bot.config import settings
from bot.database.models import Base, GeneratorState, User
from bot.database.cache import cache

logger = logging.getLogger(__name__)

# Fallback engine if Postgres is not running locally
_active_engine = None
_session_maker = None


def get_engine():
    global _active_engine, _session_maker
    if _active_engine is None:
        try:
            _active_engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                pool_pre_ping=True
            )
            _session_maker = async_sessionmaker(_active_engine, expire_on_commit=False, class_=AsyncSession)
        except Exception as e:
            logger.warning(f"Не вдалося ініціалізувати двигун {settings.DATABASE_URL}: {e}")
            fallback_url = "sqlite+aiosqlite:///data/generator.db"
            logger.info(f"Використовується резервний SQLite двигун: {fallback_url}")
            _active_engine = create_async_engine(fallback_url, echo=False)
            _session_maker = async_sessionmaker(_active_engine, expire_on_commit=False, class_=AsyncSession)
    return _active_engine


def get_session_maker():
    if _session_maker is None:
        get_engine()
    return _session_maker


async def init_db():
    global _active_engine, _session_maker
    await cache.init()

    # Try connecting with configured engine
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.warning(f"Помилка підключення до первинної БД ({e}). Перемикання на SQLite резерв...")
        fallback_url = "sqlite+aiosqlite:///data/generator.db"
        _active_engine = create_async_engine(fallback_url, echo=False)
        _session_maker = async_sessionmaker(_active_engine, expire_on_commit=False, class_=AsyncSession)
        async with _active_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    session_maker = get_session_maker()
    async with session_maker() as session:
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

        # Seed admins
        for admin_item in settings.ADMIN_IDS:
            if isinstance(admin_item, int):
                admin_user = await session.get(User, admin_item)
                if not admin_user:
                    admin_user = User(
                        user_id=admin_item,
                        username="Admin",
                        full_name="Адміністратор",
                        role="admin"
                    )
                    session.add(admin_user)
                elif admin_user.role != "admin":
                    admin_user.role = "admin"
            elif isinstance(admin_item, str):
                clean_name = admin_item.lstrip("@").lower()
                u_res = await session.execute(select(User).where(User.username.ilike(clean_name)))
                matched_u = u_res.scalar_one_or_none()
                if matched_u and matched_u.role != "admin":
                    matched_u.role = "admin"

        await session.commit()
    logger.info("База даних успішно ініціалізована.")


def async_session_maker():
    maker = get_session_maker()
    return maker()


async def get_session():
    maker = get_session_maker()
    async with maker() as session:
        yield session
