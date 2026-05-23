"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="FreightHero Watchtower", version="0.1.0")
app.include_router(router)
