"""App FastAPI do voice-onboard: custom functions + webhook pós-chamada + relatório."""

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Header, HTTPException

from . import dashboard, events, tools
from .config import get_settings
from .report import gerar_relatorio, job_relatorio_diario
from .storage import init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("voice-onboard")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db(settings.db_path)
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        job_relatorio_diario,
        CronTrigger(hour=settings.report_hour, minute=0, timezone=settings.timezone),
        id="relatorio_diario",
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    log.info(
        "voice-onboard pronto — relatório diário às %02d:00 %s",
        settings.report_hour,
        settings.timezone,
    )
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="voice-onboard webhooks", lifespan=lifespan)
app.include_router(tools.router)
app.include_router(events.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/relatorio/hoje")
async def relatorio_hoje(
    token: str = "", x_report_token: str = Header(default="")
) -> dict:
    """Pré-visualização do relatório das últimas 24h (protegida por token).

    Preferir o header X-Report-Token: a query string fica nos access logs.
    """
    settings = get_settings()
    recebido = x_report_token or token
    if not settings.report_token or not hmac.compare_digest(
        recebido, settings.report_token
    ):
        raise HTTPException(status_code=403, detail="Token inválido")
    return {"relatorio": await asyncio.to_thread(gerar_relatorio, settings.db_path)}
