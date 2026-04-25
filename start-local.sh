#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

if [ ! -f "$ROOT/api/.env" ]; then
  echo "ERROR: api/.env no existe. Copia api/.env.example y pon tu GROQ_API_KEY"
  exit 1
fi

# ── Redis ──────────────────────────────────────────────────────────────────────
echo "▶ Iniciando Redis..."
if ! command -v redis-server &>/dev/null; then
  echo "ERROR: Redis no instalado. Corre: brew install redis"
  exit 1
fi
redis-server --daemonize yes --logfile /tmp/guardiannode-redis.log
echo "✓ Redis corriendo"

# ── Python venv ────────────────────────────────────────────────────────────────
cd "$ROOT/api"
if [ ! -d ".venv" ]; then
  echo "▶ Creando virtualenv..."
  python3 -m venv .venv
fi
source .venv/bin/activate
echo "▶ Instalando dependencias Python..."
pip install -q -r requirements.txt

# ── Cargar .env ────────────────────────────────────────────────────────────────
export $(grep -v '^#' .env | xargs)

# ── Celery worker (background) ────────────────────────────────────────────────
echo "▶ Iniciando Celery worker..."
celery -A worker worker --loglevel=warning --concurrency=4 &
CELERY_PID=$!
echo "✓ Worker PID $CELERY_PID"

# ── FastAPI (background) ───────────────────────────────────────────────────────
echo "▶ Iniciando API..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
echo "✓ API PID $API_PID — http://localhost:8000"
echo "✓ Docs   — http://localhost:8000/docs"

# ── Frontend ───────────────────────────────────────────────────────────────────
cd "$ROOT/dashboard"
npm install --silent

IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GuardianNode corriendo"
echo "  Local:  http://localhost:5173"
echo "  Red:    http://$IP:5173"
echo "  WS URL para otra PC: ws://$IP:8000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Cleanup al Ctrl+C
trap "echo ''; echo 'Apagando...'; kill $CELERY_PID $API_PID 2>/dev/null; redis-cli shutdown 2>/dev/null; exit 0" INT

npm run dev -- --host 0.0.0.0
