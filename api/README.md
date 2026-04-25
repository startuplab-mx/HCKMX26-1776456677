# api/

Backend FastAPI. Ver instrucciones de ejecución en el README raíz.

## Archivos

| Archivo | Rol |
|---|---|
| `main.py` | FastAPI — endpoints REST y WebSocket |
| `analyzer.py` | Motor de análisis two-tier (regex + LLM) |
| `prefilter.py` | Tier 1: reglas regex para detección instantánea |
| `context.py` | Historial de conversación por sesión (Redis) |
| `worker.py` | Tareas Celery (análisis async) |
| `game_room.py` | WebSocket sala de juego con moderación en tiempo real |
| `ws.py` | WebSocket dashboard global |
| `models.py` | Schemas Pydantic + ORM SQLAlchemy |
| `database.py` | Configuración SQLite/Postgres |
| `config.py` | Settings desde `.env` |
