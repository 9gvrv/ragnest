from fastapi import APIRouter

from app.api import health
from app.modules.auth import router as auth_router
from app.modules.documents import router as documents_router
from app.modules.invitations import router as invitations_router
from app.modules.users import router as users_router
from app.modules.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(health.router)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_router.router)
api_v1.include_router(users_router.router)
api_v1.include_router(workspaces_router.router)
api_v1.include_router(documents_router.router)
api_v1.include_router(invitations_router.router)
api_router.include_router(api_v1)
