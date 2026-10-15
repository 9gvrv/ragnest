from fastapi import APIRouter

from app.api import health
from app.modules.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_router.router)
api_router.include_router(api_v1)
