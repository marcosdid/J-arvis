from __future__ import annotations

import time
from typing import Annotated

import psutil
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import get_db_session
from orchestrator.store.models import ClaudeSession

router = APIRouter(tags=["health"])

_startup_time = time.time()


class HealthResponse(BaseModel):
    cpu_pct: float
    mem_used_bytes: int
    mem_total_bytes: int
    uptime_seconds: int
    active_alerts_count: int


@router.get("/health", response_model=HealthResponse)
async def get_health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HealthResponse:
    mem = psutil.virtual_memory()
    alerts_count = await session.scalar(
        select(func.count())
        .select_from(ClaudeSession)
        .where(ClaudeSession.status == "awaiting_response")
    )
    return HealthResponse(
        cpu_pct=psutil.cpu_percent(interval=None),
        mem_used_bytes=mem.used,
        mem_total_bytes=mem.total,
        uptime_seconds=int(time.time() - _startup_time),
        active_alerts_count=int(alerts_count or 0),
    )
