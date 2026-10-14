from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(session: Annotated[AsyncSession, Depends(get_db)]):
    # Any database failure here means "unreachable" — a health check must never raise.
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})

    return {"status": "ok", "database": "connected"}
