# AEGIS

Sistema de moderación B2B en tiempo real para detectar reclutamiento criminal de menores en chats de videojuegos o en comentarios publicos de redes sociales.

## Problema que estamos resolviendo

La total indefensión de los menores ante la digitalización del reclutamiento del crimen organizado en México, sumada a la ineficacia de las herramientas de moderación tradicionales para entender el contexto criminal.

## Técnologias y herramientas utilizadas

## Arquitectura

```
Juego → SDK → API (FastAPI) → Cola (Celery/Redis) → Motor IA (Groq LLM)
                                                   → Logs (SQLite)
                                                   → Dashboard (WebSocket)
```

**Detección en dos niveles:**
- Tier 1: Regex/keywords — respuesta instantánea (~0ms)
- Tier 2: LLM (Llama 3.1 8B via Groq) — análisis contextual con historial de conversación

## Estructura

```
api/          Backend FastAPI + Celery
dashboard/    Frontend React (simulador de chat + dashboard)
start.sh      Levanta todo con Docker
start-local.sh  Levanta todo sin Docker (requiere brew)
docker-compose.yml
```

## Requisitos e instrucciones para correr el proyecto

- Docker Desktop **o** Redis (`brew install redis`)
- Node.js 18+
- Python 3.11+
- API key de Groq (gratis): https://console.groq.com

## Correr el proyecto

### Con Docker (recomendado)

```bash
# 1. Configurar variables
cp api/.env.example api/.env
# Editar api/.env y poner GROQ_API_KEY=gsk_...

# 2. Levantar todo
./start.sh
```

### Sin Docker

```bash
brew install redis

cp api/.env.example api/.env
# Editar api/.env y poner GROQ_API_KEY=gsk_...

./start-local.sh
```

### URLs

| Servicio | URL |
|---|---|
| Frontend (simulador) | http://localhost:5173 |
| API REST | http://localhost:8000 |
| Docs interactivos | http://localhost:8000/docs |

## Simulador multijugador

Para conectar dos PCs en la misma red:

1. Ejecutar `./start.sh` en la PC que actúa como servidor
2. Ambas PCs abren `http://<IP-servidor>:5173`
3. Usar los mismos parámetros:

| Campo | Valor |
|---|---|
| Servidor | `ws://<IP-servidor>:8000` |
| Sala | `demo` (debe ser igual en ambas) |
| Jugador | Nombre distinto en cada PC |

## Variables de entorno

Ver `api/.env.example` para la lista completa. Las esenciales:

```env
GROQ_API_KEY=gsk_...         # Requerida
LLM_PROVIDER=groq            # groq | nvidia | anthropic
API_KEY_SECRET=...           # Clave para autenticar el SDK
REDIS_URL=redis://redis:6379/0   # Docker: redis://redis:6379/0 | Local: redis://localhost:6379/0
```

## API endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/analyze/sync` | Analiza un mensaje (síncrono) |
| `POST` | `/analyze/batch` | Hasta 100 mensajes (async) |
| `GET` | `/result/{task_id}` | Consultar resultado async |
| `GET` | `/logs` | Historial de moderación |
| `GET` | `/stats` | Estadísticas para dashboard |
| `WS` | `/ws/game/{sala}` | Chat del simulador |
| `WS` | `/ws/game/{sala}/dashboard` | Alertas en tiempo real |

## Demo del prototipo



## Documentación explícita de todas las herramientas de IA utilizadas



## Integrantes del equipo

Sebastian de Jesus Cruz Cruz
Santiago Heriberto León Herrera
Alejandro Rodríguez Britto
Eduardo Arteaga Camacho
José Emilio Lopéz Flores