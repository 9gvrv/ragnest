from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from core.database import dispose_engine, engine
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health")
async def health():
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    return {"status": "ok", "database": "connected"}
