from celery import Celery
from analyzer import analyze_message
from context import push_message
from database import SessionLocal
from models import AuditLog
from config import get_settings
import json

settings = get_settings()

celery_app = Celery(
    "guardiannode",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
)


@celery_app.task(bind=True, max_retries=2)
def analyze_task(self, task_id: str, payload: dict) -> dict:
    try:
        result = analyze_message(
            message=payload["message"],
            game_id=payload.get("game_id", ""),
            session_id=payload.get("session_id", ""),
            player_id=payload.get("player_id", ""),
            target_id=payload.get("target_id", ""),
        )
        result_dict = result.model_dump()

        # Save message to conversation context (for future msgs in this session)
        push_message(
            game_id=payload["game_id"],
            session_id=payload["session_id"],
            player_id=payload["player_id"],
            target_id=payload["target_id"],
            message=payload["message"],
            risk=result.risk,
            level=result.level.value,
        )

        # Persist to audit log
        db = SessionLocal()
        try:
            log = AuditLog(
                task_id=task_id,
                game_id=payload["game_id"],
                session_id=payload["session_id"],
                player_id=payload["player_id"],
                target_id=payload["target_id"],
                message_preview=payload["message"][:100],
                raw_message=payload["message"],
                risk=result.risk,
                level=result.level.value,
                reason=result.reason,
                action=result.action.value,
            )
            db.add(log)
            db.commit()

            if result.risk:
                _publish_alert(log, result_dict)
        finally:
            db.close()

        return result_dict

    except Exception as exc:
        raise self.retry(exc=exc, countdown=3)


def _publish_alert(log: AuditLog, result: dict):
    import redis as redis_lib
    r = redis_lib.from_url(settings.redis_url)
    alert = {
        "task_id": log.task_id,
        "game_id": log.game_id,
        "player_id": log.player_id,
        "level": result["level"],
        "reason": result["reason"],
        "action": result["action"],
    }
    r.publish("guardiannode:alerts", json.dumps(alert))
