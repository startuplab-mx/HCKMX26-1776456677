#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ── 1. Check .env ──────────────────────────────────────────────────────────────
if [ ! -f "$ROOT/api/.env" ]; then
  echo "ERROR: api/.env no existe. Copia api/.env.example y pon tu GROQ_API_KEY"
  echo "  cp api/.env.example api/.env"
  exit 1
fi

if ! grep -q "GROQ_API_KEY=gsk_" "$ROOT/api/.env" 2>/dev/null; then
  echo "ADVERTENCIA: GROQ_API_KEY no configurada en api/.env"
  echo "  Obtén tu key gratis en https://console.groq.com"
  echo ""
fi

# ── 2. Backend (Redis + API + Worker via Docker Compose) ──────────────────────
echo "▶ Iniciando backend (Docker Compose)..."
cd "$ROOT"
docker compose up -d --build
echo "✓ API corriendo en http://localhost:8000"
echo "✓ Docs en     http://localhost:8000/docs"

# ── 3. Frontend ────────────────────────────────────────────────────────────────
echo ""
echo "▶ Iniciando frontend..."
cd "$ROOT/dashboard"
npm install --silent
echo "✓ Frontend en http://localhost:5173"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GuardianNode corriendo."
echo "  Abre http://localhost:5173 en el navegador"
echo "  Para conectar otra PC usa: ws://$(ipconfig getifaddr en0 2>/dev/null || hostname -I | awk '{print $1}'):8000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
npm run dev -- --host 0.0.0.0
