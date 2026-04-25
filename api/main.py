import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from config import get_settings
from database import init_db, get_db
from models import MessageIn, SocialMediaIn, TaskResponse, AnalysisResult, LogEntry, AuditLog
from worker import celery_app, analyze_task
from ws import router as ws_router
from game_room import router as game_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="GuardianNode API",
    description="Real-time child safety moderation for gaming platforms",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router)
app.include_router(game_router)


# ── Auth ───────────────────────────────────────────────────────────────────────

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key_secret:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post(
    "/analyze",
    response_model=TaskResponse,
    status_code=202,
    summary="Submit single message (async)",
    dependencies=[Depends(verify_api_key)],
)
def submit_message(payload: MessageIn):
    task_id = str(uuid.uuid4())
    analyze_task.apply_async(
        args=[task_id, payload.model_dump(mode="json")],
        task_id=task_id,
    )
    return TaskResponse(task_id=task_id, status="queued")


@app.get(
    "/result/{task_id}",
    response_model=TaskResponse,
    summary="Poll analysis result",
    dependencies=[Depends(verify_api_key)],
)
def get_result(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return TaskResponse(task_id=task_id, status="queued")
    if task.state == "STARTED":
        return TaskResponse(task_id=task_id, status="processing")
    if task.state == "SUCCESS":
        return TaskResponse(
            task_id=task_id,
            status="done",
            result=AnalysisResult(**task.result),
        )
    if task.state == "FAILURE":
        return TaskResponse(task_id=task_id, status="error")
    return TaskResponse(task_id=task_id, status=task.state.lower())


@app.post(
    "/analyze/sync",
    response_model=AnalysisResult,
    summary="Sync analysis — no queue, result immediate",
    dependencies=[Depends(verify_api_key)],
)
def analyze_sync(payload: MessageIn, db: Session = Depends(get_db)):
    from analyzer import analyze_message
    from context import push_message

    result = analyze_message(
        message=payload.message,
        game_id=payload.game_id,
        session_id=payload.session_id,
        player_id=payload.player_id,
        target_id=payload.target_id,
    )
    push_message(
        game_id=payload.game_id,
        session_id=payload.session_id,
        player_id=payload.player_id,
        target_id=payload.target_id,
        message=payload.message,
        risk=result.risk,
        level=result.level.value,
    )
    _save_log(db, str(uuid.uuid4()), payload, result)
    return result


@app.post(
    "/analyze/batch",
    response_model=list[TaskResponse],
    status_code=202,
    summary="Submit up to 100 messages in one call (async)",
    dependencies=[Depends(verify_api_key)],
)
def submit_batch(payloads: list[MessageIn]):
    """
    SDK sends N messages per call instead of N separate HTTP requests.
    Each message gets its own task_id. Tier-1 pre-filter runs inline (0ms),
    only ambiguous messages hit the LLM queue.
    """
    if len(payloads) > 100:
        raise HTTPException(status_code=422, detail="Max 100 messages per batch")

    from prefilter import prefilter

    results = []
    for payload in payloads:
        task_id = str(uuid.uuid4())
        fast = prefilter(payload.message)
        if fast is not None:
            # Tier 1 fired — no queue needed, return immediately
            results.append(TaskResponse(task_id=task_id, status="done", result=fast))
        else:
            analyze_task.apply_async(
                args=[task_id, payload.model_dump(mode="json")],
                task_id=task_id,
            )
            results.append(TaskResponse(task_id=task_id, status="queued"))
    return results


@app.post(
    "/analyze/batch/sync",
    response_model=list[AnalysisResult],
    summary="Sync batch — all results in one response (max 50)",
    dependencies=[Depends(verify_api_key)],
)
async def analyze_batch_sync(payloads: list[MessageIn], db: Session = Depends(get_db)):
    """
    Best for low-volume, latency-sensitive use cases.
    Runs Tier-1 inline, Tier-2 LLM calls in parallel via asyncio.
    """
    if len(payloads) > 50:
        raise HTTPException(status_code=422, detail="Max 50 messages per sync batch")

    from prefilter import prefilter
    from analyzer import analyze_message

    async def _analyze_one(payload: MessageIn) -> AnalysisResult:
        fast = prefilter(payload.message)
        if fast is not None:
            return fast
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, analyze_message, payload.message)

    results = await asyncio.gather(*[_analyze_one(p) for p in payloads])

    for payload, result in zip(payloads, results):
        _save_log(db, str(uuid.uuid4()), payload, result)

    return list(results)


@app.get(
    "/logs",
    response_model=list[LogEntry],
    summary="Query audit logs",
    dependencies=[Depends(verify_api_key)],
)
def get_logs(
    db: Session = Depends(get_db),
    game_id: Optional[str] = Query(None),
    risk_only: bool = Query(False),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
):
    query = db.query(AuditLog)
    if game_id:
        query = query.filter(AuditLog.game_id == game_id)
    if risk_only:
        query = query.filter(AuditLog.risk == True)
    return query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()


@app.post(
    "/analyze/social",
    response_model=AnalysisResult,
    summary="Analizar comentario de red social (TikTok/Instagram)",
    dependencies=[Depends(verify_api_key)],
)
def analyze_social_comment(payload: SocialMediaIn, db: Session = Depends(get_db)):
    from social_analyzer import analyze_social

    result = analyze_social(payload)

    log = AuditLog(
        task_id=str(uuid.uuid4()),
        game_id=payload.platform_id,
        session_id=payload.post_id,
        player_id=payload.commenter_id,
        target_id=payload.creator_id,
        message_preview=payload.comment[:100],
        raw_message=payload.comment,
        risk=result.risk,
        level=result.level.value,
        reason=result.reason,
        action=result.action.value,
    )
    db.add(log)
    db.commit()
    return result


@app.get(
    "/stats",
    summary="Dashboard stats — counts by level and game",
    dependencies=[Depends(verify_api_key)],
)
def get_stats(
    db: Session = Depends(get_db),
    game_id: Optional[str] = Query(None),
):
    from sqlalchemy import func

    q = db.query(AuditLog)
    if game_id:
        q = q.filter(AuditLog.game_id == game_id)

    total = q.count()
    risky = q.filter(AuditLog.risk == True).count()

    level_counts = (
        db.query(AuditLog.level, func.count(AuditLog.id))
        .filter(AuditLog.risk == True)
        .group_by(AuditLog.level)
        .all()
    )
    action_counts = (
        db.query(AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.action)
        .all()
    )
    top_games = (
        db.query(AuditLog.game_id, func.count(AuditLog.id).label("alerts"))
        .filter(AuditLog.risk == True)
        .group_by(AuditLog.game_id)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
        .all()
    )

    return {
        "total_messages": total,
        "total_alerts": risky,
        "alert_rate": round(risky / total, 4) if total else 0,
        "by_level": {level: count for level, count in level_counts},
        "by_action": {action: count for action, count in action_counts},
        "top_games_by_alerts": [
            {"game_id": g, "alerts": c} for g, c in top_games
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "guardiannode-api"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _save_log(db: Session, task_id: str, payload: MessageIn, result: AnalysisResult):
    log = AuditLog(
        task_id=task_id,
        game_id=payload.game_id,
        session_id=payload.session_id,
        player_id=payload.player_id,
        target_id=payload.target_id,
        message_preview=payload.message[:100],
        raw_message=payload.message,
        risk=result.risk,
        level=result.level.value,
        reason=result.reason,
        action=result.action.value,
    )
    db.add(log)
    db.commit()
