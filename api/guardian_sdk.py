import requests
import time
import uuid
import logging
from typing import List, Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GuardianNodeSDK")

class GuardianNodeSDK:
    """
    Official SDK for GuardianNode API.
    Provides real-time child safety moderation for gaming platforms.
    """
    
    def __init__(self, endpoint: str, api_key: str, game_id: str):
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key
        self.game_id = game_id
        self._headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def analyze_message(self, player_id: str, message: str, target_id: str = "room", session_id: str = "default") -> Dict[str, Any]:
        """
        Analyzes a single message synchronously.
        Best for real-time chat where immediate blocking is required.
        """
        payload = {
            "game_id": self.game_id,
            "session_id": session_id,
            "player_id": player_id,
            "target_id": target_id,
            "message": message,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        try:
            response = requests.post(
                f"{self.endpoint}/analyze/sync", 
                json=payload, 
                headers=self._headers, 
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            
            logger.error(f"API Error: {response.status_code} - {response.text}")
            return self._fallback_result("API_ERROR")
        except requests.exceptions.Timeout:
            logger.warning("API Timeout - applying fallback")
            return self._fallback_result("TIMEOUT")
        except Exception as e:
            logger.error(f"SDK Exception: {str(e)}")
            return self._fallback_result("CONNECTION_FAILED")

    def analyze_batch(self, messages: List[Dict[str, str]], sync: bool = True) -> List[Dict[str, Any]]:
        """
        Analyzes multiple messages in a single call.
        'messages' should be a list of dicts with: player_id, message, target_id, session_id.
        """
        payloads = []
        for m in messages:
            payloads.append({
                "game_id": self.game_id,
                "session_id": m.get("session_id", "default"),
                "player_id": m["player_id"],
                "target_id": m.get("target_id", "room"),
                "message": m["message"]
            })
            
        path = "/analyze/batch/sync" if sync else "/analyze/batch"
        
        try:
            response = requests.post(
                f"{self.endpoint}{path}", 
                json=payloads, 
                headers=self._headers, 
                timeout=10
            )
            if response.status_code in [200, 202]:
                return response.json()
            return [self._fallback_result("BATCH_ERROR")] * len(messages)
        except Exception as e:
            logger.error(f"Batch SDK Exception: {str(e)}")
            return [self._fallback_result("BATCH_FAILED")] * len(messages)

    def get_stats(self) -> Dict[str, Any]:
        """Fetch game-specific moderation stats."""
        try:
            response = requests.get(
                f"{self.endpoint}/stats?game_id={self.game_id}", 
                headers=self._headers
            )
            return response.json() if response.status_code == 200 else {}
        except Exception:
            return {}

    def _fallback_result(self, reason: str) -> Dict[str, Any]:
        """Safety fallback: when in doubt, warn (Fail-Close)."""
        return {
            "risk": True,
            "level": "medium",
            "reason": f"SDK_FALLBACK: {reason}",
            "action": "warn"
        }

# Usage Example
if __name__ == "__main__":
    sdk = GuardianNodeSDK(
        endpoint="http://localhost:8000",
        api_key="guardiannode-dev-secret",
        game_id="my-awesome-game"
    )
    
    print("Testing single message...")
    result = sdk.analyze_message("player123", "pasa tu whatsapp")
    print(f"Action: {result['action']} | Reason: {result['reason']}")
