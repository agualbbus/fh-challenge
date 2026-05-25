"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router, write_router
from app.customers.base import get_customer_profiles


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_customer_profiles()
    yield


app = FastAPI(title="FreightHero Watchtower", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.include_router(write_router)
