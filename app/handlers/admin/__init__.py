from aiogram import Router

from app.handlers.admin.messaging_handlers import router as messaging_router
from app.handlers.admin.stats_handlers import router as stats_router

router = Router()
router.include_router(stats_router)
router.include_router(messaging_router)
