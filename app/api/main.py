"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router, write_router
from app.config import get_settings
from app.customers.base import get_customer_profiles
from app.worker.checkpointer import close_checkpointer, init_checkpointer


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_customer_profiles()
    app.state.checkpointer = await init_checkpointer(get_settings().database_url)
    try:
        yield
    finally:
        await close_checkpointer()


app = FastAPI(title="FreightHero Watchtower", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(write_router)
