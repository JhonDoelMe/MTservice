from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from bot.config import settings
from bot.database.models import Base, GeneratorState, User

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        # Check if default generator exists
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

        # Seed admins if any
        for admin_id in settings.ADMIN_IDS:
            admin_user = await session.get(User, admin_id)
            if not admin_user:
                admin_user = User(
                    user_id=admin_id,
                    username="Admin",
                    full_name="Administrator",
                    role="admin"
                )
                session.add(admin_user)
            elif admin_user.role != "admin":
                admin_user.role = "admin"

        await session.commit()


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
