from aiogram import Dispatcher
from bot.handlers.common import common_router
from bot.handlers.generator import generator_router
from bot.handlers.fuel import fuel_router
from bot.handlers.maintenance import maintenance_router
from bot.handlers.reports import reports_router
from bot.handlers.admin import admin_router


def setup_routers(dp: Dispatcher):
    dp.include_router(common_router)
    dp.include_router(generator_router)
    dp.include_router(fuel_router)
    dp.include_router(maintenance_router)
    dp.include_router(reports_router)
    dp.include_router(admin_router)
