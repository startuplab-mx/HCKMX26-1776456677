import asyncio
import websockets
import json

async def monitor():
    uri = "ws://127.0.0.1:8888/ws/game/sala-demo-unity/supervisor"
    print(f"📡 Radar activado en {uri}...")
    try:
        # Versión ultra-simple sin headers, ya que abrimos el CORS
        async with websockets.connect(uri) as websocket:
            print("✅ ¡SUPERVISOR CONECTADO! Esperando mensaje...\n")
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                if data.get("type") == "supervisor_message":
                    print("="*40)
                    print(f"💎 ¡MENSAJE CAPTURADO!")
                    print(f"👤 Usuario: {data.get('from')}")
                    print(f"💬 Texto: {data.get('text')}")
                    print(f"🛡️ Nivel: {data.get('level')}")
                    print("="*40)
                    break 
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(monitor())
