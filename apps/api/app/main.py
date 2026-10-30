from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine
from app.modules.documents.middleware import UploadSizeLimitMiddleware


def create_app() -> FastAPI:
    configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await dispose_engine()

    app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
    app.add_middleware(UploadSizeLimitMiddleware)
    app.include_router(api_router)
    return app


app = create_app()
