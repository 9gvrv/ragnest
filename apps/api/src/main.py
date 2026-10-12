from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from src.api.routes import api_router
from src.config import settings
from src.db import dispose_engine, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/health")
async def health():
    async with engine.connect() as conn:
        await conn.execute(text("select 1"))
    return {"status": "ok", "database": "connected"}
