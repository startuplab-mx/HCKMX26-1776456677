"""
AEGIS Python SDK — REST client.

Sync and async variants. Use AEGISClient for regular code,
AEGISAsyncClient inside asyncio / FastAPI / etc.
"""
import httpx
from typing import Optional
from .models import AnalysisResult, MessagePayload


class AEGISClient:
    """Synchronous REST client."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key:  str = "aegis-dev-secret",
        timeout:  float = 15.0,
    ):
        self._http = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    # ── Core ───────────────────────────────────────────────────────────────────

    def analyze(
        self,
        message:    str,
        player_id:  str,
        target_id:  str,
        game_id:    str = "default",
        session_id: str = "default",
    ) -> AnalysisResult:
        """Analyze one message. Blocks until result is ready (~500ms)."""
        payload = MessagePayload(message, player_id, target_id, game_id, session_id)
        resp = self._http.post("/analyze/sync", json=payload.to_dict())
        resp.raise_for_status()
        return AnalysisResult.from_dict(resp.json())

    def analyze_batch(
        self,
        messages: list[MessagePayload],
    ) -> list[AnalysisResult]:
        """Analyze up to 50 messages in one call (sync, parallel LLM calls)."""
        if len(messages) > 50:
            raise ValueError("Max 50 messages per sync batch")
        body = [m.to_dict() for m in messages]
        resp = self._http.post("/analyze/batch/sync", json=body)
        resp.raise_for_status()
        return [AnalysisResult.from_dict(r) for r in resp.json()]

    # ── Convenience ────────────────────────────────────────────────────────────

    def is_safe(self, message: str, player_id: str, target_id: str, **kwargs) -> bool:
        """Returns True if message is safe to send."""
        result = self.analyze(message, player_id, target_id, **kwargs)
        return not result.risk

    def should_block(self, message: str, player_id: str, target_id: str, **kwargs) -> bool:
        result = self.analyze(message, player_id, target_id, **kwargs)
        return result.is_blocked

    # ── Stats / Logs ───────────────────────────────────────────────────────────

    def stats(self, game_id: Optional[str] = None) -> dict:
        params = {"game_id": game_id} if game_id else {}
        resp = self._http.get("/stats", params=params)
        resp.raise_for_status()
        return resp.json()

    def logs(
        self,
        game_id:   Optional[str] = None,
        risk_only: bool = True,
        limit:     int = 50,
    ) -> list[dict]:
        params = {"risk_only": risk_only, "limit": limit}
        if game_id:
            params["game_id"] = game_id
        resp = self._http.get("/logs", params=params)
        resp.raise_for_status()
        return resp.json()

    def health(self) -> bool:
        try:
            return self._http.get("/health").json().get("status") == "ok"
        except Exception:
            return False

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class AEGISAsyncClient:
    """Async REST client for use with asyncio / FastAPI."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key:  str = "aegis-dev-secret",
        timeout:  float = 15.0,
    ):
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout,
        )

    async def analyze(
        self,
        message:    str,
        player_id:  str,
        target_id:  str,
        game_id:    str = "default",
        session_id: str = "default",
    ) -> AnalysisResult:
        payload = MessagePayload(message, player_id, target_id, game_id, session_id)
        resp = await self._http.post("/analyze/sync", json=payload.to_dict())
        resp.raise_for_status()
        return AnalysisResult.from_dict(resp.json())

    async def analyze_batch(self, messages: list[MessagePayload]) -> list[AnalysisResult]:
        body = [m.to_dict() for m in messages]
        resp = await self._http.post("/analyze/batch/sync", json=body)
        resp.raise_for_status()
        return [AnalysisResult.from_dict(r) for r in resp.json()]

    async def stats(self, game_id: Optional[str] = None) -> dict:
        params = {"game_id": game_id} if game_id else {}
        resp = await self._http.get("/stats", params=params)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()
