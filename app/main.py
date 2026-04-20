"""
FastAPI entry point.

Responsibilities at startup:
  * configure logging
  * open asyncpg pool
  * start the APScheduler daily-summary job
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from .config import get_settings
from .routers import ops, webhook
from .services import db, daily_summary
from .utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("main")

_scheduler: AsyncIOScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("app.starting", env=settings.app_env)

    missing = settings.assert_ready_for_runtime()
    if missing:
        log.warning("app.missing_config", missing=missing)

    await db.init_pool()

    # Schedule daily summary
    global _scheduler
    if settings.is_production and not missing:
        _scheduler = AsyncIOScheduler(timezone=settings.default_timezone)
        _scheduler.add_job(
            daily_summary.run_daily_summary_for_all,
            CronTrigger(hour=settings.daily_summary_hour, minute=0),
            id="daily_summary",
            replace_existing=True,
        )
        _scheduler.start()
        log.info("scheduler.started", hour=settings.daily_summary_hour)

    yield

    if _scheduler:
        _scheduler.shutdown(wait=False)
    await db.close_pool()
    log.info("app.stopped")


app = FastAPI(
    title="Kirana Bookkeeper",
    version="0.1.0",
    description="WhatsApp AI bookkeeping agent for Pakistani kirana shops.",
    lifespan=lifespan,
)

app.include_router(ops.router)
app.include_router(webhook.router)
