from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RiskLevel(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class Action(str, Enum):
    allow = "allow"
    warn  = "warn"
    block = "block"


@dataclass
class AnalysisResult:
    risk:   bool
    level:  RiskLevel
    reason: str
    action: Action

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisResult":
        return cls(
            risk=d["risk"],
            level=RiskLevel(d["level"]),
            reason=d["reason"],
            action=Action(d["action"]),
        )

    @property
    def is_blocked(self) -> bool:
        return self.action == Action.block

    @property
    def is_warned(self) -> bool:
        return self.action == Action.warn


@dataclass
class MessagePayload:
    message:    str
    player_id:  str
    target_id:  str
    game_id:    str        = "default"
    session_id: str        = "default"

    def to_dict(self) -> dict:
        return {
            "message":    self.message,
            "player_id":  self.player_id,
            "target_id":  self.target_id,
            "game_id":    self.game_id,
            "session_id": self.session_id,
        }


@dataclass
class AlertEvent:
    level:   RiskLevel
    reason:  str
    action:  Action
    from_:   str
    text:    str
    room:    str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "AlertEvent":
        return cls(
            level=RiskLevel(d.get("level", "low")),
            reason=d.get("reason", ""),
            action=Action(d.get("action", "allow")),
            from_=d.get("from", ""),
            text=d.get("text", ""),
            room=d.get("room", ""),
        )


@dataclass
class ChatMessage:
    from_:   str
    text:    str
    level:   RiskLevel
    warned:  bool
    blocked: bool
    reason:  str

    @classmethod
    def from_dict(cls, d: dict) -> "ChatMessage":
        return cls(
            from_=d.get("from", ""),
            text=d.get("text", ""),
            level=RiskLevel(d.get("level", "low")),
            warned=d.get("warned", False),
            blocked=d.get("type") == "blocked",
            reason=d.get("reason", ""),
        )
