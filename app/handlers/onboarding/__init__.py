from aiogram import Router

from app.handlers.onboarding.join import router as join_router
from app.handlers.onboarding.pd import router as pd_router
from app.handlers.onboarding.rules import router as rules_router
from app.handlers.onboarding.start import router as start_router

router = Router()
router.include_router(start_router)
router.include_router(rules_router)
router.include_router(pd_router)
router.include_router(join_router)
