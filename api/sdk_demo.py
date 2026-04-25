
import requests
import time
from typing import List, Dict

class AegisSDK:
    def __init__(self, endpoint: str, api_key: str, game_id: str):
        self.endpoint = endpoint
        self.api_key = api_key
        self.game_id = game_id
        self.session_id = "session_default"

    def analyze_message(self, player_id: str, target_id: str, message: str) -> Dict:
        """
        Llamada síncrona (Tier 1 + Tier 2). 
        Usa esto para mensajes críticos.
        """
        payload = {
            "game_id": self.game_id,
            "session_id": self.session_id,
            "player_id": player_id,
            "target_id": target_id,
            "message": message,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        headers = {"x-api-key": self.api_key}
        
        try:
            response = requests.post(f"{self.endpoint}/analyze/sync", json=payload, headers=headers, timeout=5)
            if response.status_code == 200:
                return response.json()
            return self._local_fallback("API_ERROR")
        except Exception:
            return self._local_fallback("CONNECTION_TIMEOUT")

    def _local_fallback(self, reason: str):
        """Si todo falla, el SDK decide qué hacer localmente."""
        return {
            "risk": True,
            "level": "medium",
            "reason": f"SDK_FALLBACK: {reason}",
            "action": "warn"
        }

# --- DEMO DE INTEGRACIÓN ---
if __name__ == "__main__":
    # Configuración
    sdk = AegisSDK(
        endpoint="http://localhost:8000",
        api_key="guardiannode-dev-secret",
        game_id="fortnite-clone-01"
    )

    print("🛡️ Simulando chat del juego...")
    
    mensajes = [
        ("Jugador1", "Amigo", "hola, buen juego!"),
        ("Jugador1", "Amigo", "pasa tu whatsapp para hablar"),
        ("Jugador2", "Extraño", "cuantos años tienes?")
    ]

    for p_from, p_to, msg in mensajes:
        print(f"\n[{p_from} -> {p_to}]: {msg}")
        res = sdk.analyze_message(p_from, p_to, msg)
        
        if res["action"] == "block":
            print(f"❌ MENSAJE BLOQUEADO: {res['reason']}")
        elif res["action"] == "warn":
            print(f"⚠️ ALERTA: {res['reason']}")
        else:
            print(f"✅ MENSAJE PERMITIDO")
