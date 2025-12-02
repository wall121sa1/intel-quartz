import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import AppConfig, load_config
from .dashboard import router as dashboard_router
from .db import create_all_tables, init_db
from .release_scheduler import start_release_scheduler
from .rss_api import router as rss_router
from .telegram_poller import start_telegram_pollers


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: AppConfig = load_config()
    app.state.config = config

    init_db(config.database.url)
    create_all_tables()

    poller_task = asyncio.create_task(start_telegram_pollers(config))
    release_task = asyncio.create_task(start_release_scheduler(config))

    try:
        yield
    finally:
        for task in (poller_task, release_task):
            task.cancel()
        await asyncio.gather(poller_task, release_task, return_exceptions=True)


app = FastAPI(lifespan=lifespan)

app.include_router(dashboard_router)
app.include_router(rss_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
