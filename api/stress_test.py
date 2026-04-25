import asyncio
import httpx
import time
import random
import sys
from typing import List, Dict

# Test messages based on prefilter rules and general safety
MESSAGES = {
    "normal": [
        "Hola, ¿cómo estás?",
        "¿Quieres jugar una partida?",
        "¡Buen juego!",
        "Necesito ayuda con esta misión",
        "¿A qué hora empezamos?",
        "Me gusta mucho este juego",
        "¿Alguien tiene munición?",
        "GGEP",
        "Vamos por la derecha",
        "¡Cuidado con el enemigo!"
    ],
    "warning": [
        "¿Cuántos años tienes?",
        "¿En qué grado estás?",
        "¿Vas a la escuela?",
        "Skins gratis si me agregas",
        "Confía en mí, soy tu amigo",
        "Tus padres no te entienden como yo",
        "¿Tienes novio?",
        "Te regalo ítems si hablamos por privado",
        "¿Estás solo en casa?",
        "Eres muy linda, ¿lo sabías?"
    ],
    "blocked": [
        "Pásame tu whatsapp para hablar",
        "Manda nudes o comparto tus fotos",
        "¿Dónde vives? Quiero ir a verte",
        "Te pago dinero fácil si mueves un paquete",
        "No le digas a tus papás que hablamos",
        "Hagamos videollamada por discord",
        "Quiero que nos veamos a solas",
        "Mastúrbate en cámara para mí",
        "Borra este chat después de leerlo",
        "Pasa tu número de cel"
    ]
}

async def send_request(client: httpx.AsyncClient, api_url: str, api_key: str, category: str, message: str) -> Dict:
    payload = {
        "game_id": "stress-test-game",
        "session_id": f"session-{random.randint(1000, 9999)}",
        "player_id": f"player-{random.randint(1, 100)}",
        "target_id": "target-0",
        "message": message
    }
    
    start_time = time.perf_counter()
    try:
        response = await client.post(
            api_url,
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=20.0
        )
        end_time = time.perf_counter()
        
        if response.status_code == 200:
            result = response.json()
            return {
                "category": category,
                "status": "success",
                "latency": end_time - start_time,
                "action": result.get("action"),
                "expected": "allow" if category == "normal" else ("warn" if category == "warning" else "block")
            }
        else:
            return {
                "category": category,
                "status": "error",
                "code": response.status_code,
                "content": response.text[:100],
                "latency": end_time - start_time
            }
    except Exception as e:
        end_time = time.perf_counter()
        return {
            "category": category,
            "status": "exception",
            "error": str(e),
            "latency": end_time - start_time
        }

async def run_stress_test(api_url: str, api_key: str, concurrency: int, total_requests: int):
    print(f"Starting stress test on {api_url}")
    print(f"Concurrency: {concurrency}, Total Requests: {total_requests}")
    
    tasks = []
    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(concurrency)
        
        async def sem_task(category, message):
            async with semaphore:
                return await send_request(client, api_url, api_key, category, message)
        
        for i in range(total_requests):
            category = random.choice(list(MESSAGES.keys()))
            message = random.choice(MESSAGES[category])
            tasks.append(sem_task(category, message))
        
        results = await asyncio.gather(*tasks)
    
    summary = {
        "normal": {"count": 0, "success": 0, "errors": 0, "latencies": [], "actions": {}},
        "warning": {"count": 0, "success": 0, "errors": 0, "latencies": [], "actions": {}},
        "blocked": {"count": 0, "success": 0, "errors": 0, "latencies": [], "actions": {}}
    }
    
    total_success = 0
    total_errors = 0
    
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in summary: summary[cat] = {"count": 0, "success": 0, "errors": 0, "latencies": [], "actions": {}}
        
        summary[cat]["count"] += 1
        if r["status"] == "success":
            summary[cat]["success"] += 1
            summary[cat]["latencies"].append(r["latency"])
            total_success += 1
            action = r.get("action", "none")
            summary[cat]["actions"][action] = summary[cat]["actions"].get(action, 0) + 1
        else:
            summary[cat]["errors"] += 1
            total_errors += 1
            
    print("\n--- Stress Test Results ---")
    print(f"Total Requests: {total_requests}")
    print(f"Successful:     {total_success}")
    print(f"Errors/Failed:  {total_errors}")
    
    for cat, data in summary.items():
        if data["count"] == 0: continue
        avg_lat = sum(data["latencies"]) / len(data["latencies"]) if data["latencies"] else 0
        success_rate = (data["success"] / data["count"]) * 100
        print(f"\n[{cat.upper()}] ({data['count']} requests)")
        print(f"  Success Rate:   {success_rate:.1f}%")
        print(f"  Avg Latency:    {avg_lat:.3f}s")
        if data["latencies"]:
            print(f"  Min/Max:        {min(data['latencies']):.3f}s / {max(data['latencies']):.3f}s")
        print(f"  Actions:        {data['actions']}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python stress_test.py <url> <api_key> [concurrency] [total]")
        sys.exit(1)
        
    url = sys.argv[1]
    key = sys.argv[2]
    concurrency = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    total = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    
    asyncio.run(run_stress_test(url, key, concurrency, total))
