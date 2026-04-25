from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer
from sqlalchemy.orm import declarative_base

Base = declarative_base()


# ── Enums ──────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Action(str, Enum):
    allow = "allow"
    warn = "warn"
    block = "block"


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class MessageIn(BaseModel):
    """Payload sent by the game SDK."""
    game_id: str = Field(..., description="Unique game/platform identifier")
    session_id: str = Field(..., description="Active game session")
    player_id: str = Field(..., description="Sender player ID (hashed by SDK)")
    target_id: str = Field(..., description="Receiver player ID (hashed by SDK)")
    message: str = Field(..., max_length=2000)
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class PlatformContext(BaseModel):
    platform: str = Field(..., description="tiktok | instagram | youtube | twitter")
    post_description: Optional[str] = Field(None, max_length=500)
    post_hashtags: Optional[list[str]] = Field(default_factory=list)
    account_age_days: Optional[int] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    creator_is_minor: Optional[bool] = None


class SocialMediaIn(BaseModel):
    """Payload for social media comment analysis."""
    platform_id: str = Field(..., description="Platform identifier, e.g. 'tiktok-prod'")
    post_id: str = Field(..., description="Post/video being commented on")
    commenter_id: str = Field(..., description="Hashed commenter account ID")
    creator_id: str = Field(..., description="Hashed content creator ID")
    comment: str = Field(..., max_length=2000)
    context: Optional[PlatformContext] = None
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class AnalysisResult(BaseModel):
    risk: bool
    level: RiskLevel
    reason: str = Field(..., max_length=100)
    action: Action


class TaskResponse(BaseModel):
    task_id: str
    status: str  # "queued" | "processing" | "done" | "error"
    result: Optional[AnalysisResult] = None


class LogEntry(BaseModel):
    id: int
    game_id: str
    session_id: str
    player_id: str
    target_id: str
    message_preview: str
    risk: bool
    level: str
    reason: str
    action: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── SQLAlchemy ORM ─────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), index=True)
    game_id = Column(String(128), index=True)
    session_id = Column(String(128))
    player_id = Column(String(128))
    target_id = Column(String(128))
    message_preview = Column(String(100))  # first 100 chars only
    risk = Column(Boolean, default=False)
    level = Column(String(16))
    reason = Column(String(200))
    action = Column(String(16))
    raw_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
