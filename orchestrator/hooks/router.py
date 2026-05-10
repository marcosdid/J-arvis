from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api._deps import (
    get_db_session,
    resolve_broadcaster,
    resolve_notifier,
    resolve_token_registry,
)
from orchestrator.core.sessions import SessionStatus, bump_last_hook_at, update_status
from orchestrator.events.broadcaster import WsBroadcaster
from orchestrator.events.envelope import WsEvent
from orchestrator.hooks.parser import (
    InvalidHookPayloadError,
    parse_notification,
    parse_pretooluse,
    parse_stop,
)
from orchestrator.hooks.tokens import TokenRegistry
from orchestrator.notifications.sink import NotifierSink, should_notify
from orchestrator.store.models import ClaudeSession, Project, Worktree

router = APIRouter()


def _notify_text(s: SessionStatus) -> tuple[str, str]:
    if s == SessionStatus.AWAITING_RESPONSE:
        return "Aguarda você", "dialog-information"
    return "Concluído", "emblem-default"


async def _summary(session: AsyncSession, session_id: str) -> str:
    row = await session.get(ClaudeSession, session_id)
    if row is None:  # pragma: no cover
        return "?"
    wt = await session.get(Worktree, row.worktree_id)
    if wt is None:  # pragma: no cover
        return "?"
    proj = await session.get(Project, wt.project_id)
    name = proj.name if proj else "?"
    branch = wt.branch or "(detached)"
    return f"J-arvis · {name} · {branch}"


def _resolve_or_404(token: str, registry: TokenRegistry) -> str:
    sid = registry.resolve(token)
    if sid is None:
        raise HTTPException(status_code=404)
    return sid


async def _fetch_task_id(db: AsyncSession, session_id: str) -> str:
    row = await db.get(ClaudeSession, session_id)
    if row is None:  # pragma: no cover
        raise HTTPException(status_code=404)
    return row.task_id


@router.post("/hooks/Notification/{token}", status_code=204)
async def hook_notification(
    token: str,
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[TokenRegistry, Depends(resolve_token_registry)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
    notifier: Annotated[NotifierSink, Depends(resolve_notifier)],
) -> None:
    sid = _resolve_or_404(token, registry)
    tid = await _fetch_task_id(db, sid)

    try:
        new_status = parse_notification(payload)
    except InvalidHookPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    prev, new = await update_status(db, sid, new_status)
    if prev != new:
        await broadcaster.publish(
            WsEvent.session_status(
                session_id=sid,
                task_id=tid,
                new_status=new,
                previous_status=prev,
            )
        )
    if should_notify(prev, new):
        body, icon = _notify_text(new)
        await notifier.notify(summary=await _summary(db, sid), body=body, icon=icon)


@router.post("/hooks/PreToolUse/{token}")
async def hook_pretooluse(
    token: str,
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[TokenRegistry, Depends(resolve_token_registry)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
) -> dict[str, bool]:
    sid = _resolve_or_404(token, registry)
    tid = await _fetch_task_id(db, sid)

    try:
        tool = parse_pretooluse(payload)
    except InvalidHookPayloadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await bump_last_hook_at(db, sid)
    await broadcaster.publish(WsEvent.session_tool_use(session_id=sid, task_id=tid, tool=tool))
    return {"continue": True}


@router.post("/hooks/Stop/{token}", status_code=204)
async def hook_stop(
    token: str,
    payload: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    registry: Annotated[TokenRegistry, Depends(resolve_token_registry)],
    broadcaster: Annotated[WsBroadcaster, Depends(resolve_broadcaster)],
    notifier: Annotated[NotifierSink, Depends(resolve_notifier)],
) -> None:
    sid = _resolve_or_404(token, registry)
    tid = await _fetch_task_id(db, sid)

    new_status = parse_stop(payload)
    prev, new = await update_status(db, sid, new_status)
    if prev != new:
        await broadcaster.publish(
            WsEvent.session_status(
                session_id=sid,
                task_id=tid,
                new_status=new,
                previous_status=prev,
            )
        )
        await broadcaster.publish(WsEvent.session_stopped(session_id=sid, task_id=tid))
    if should_notify(prev, new):
        body, icon = _notify_text(new)
        await notifier.notify(summary=await _summary(db, sid), body=body, icon=icon)
