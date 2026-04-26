# AEGIS — Sistema de Moderación Infantil en Tiempo Real

> **Hackathon de Seguridad Digital Infantil · CDMX 2026**

---

## Descripción

AEGIS es un SDK de moderación B2B que protege a menores de edad en plataformas de videojuegos y redes sociales, detectando en tiempo real dos amenazas críticas en el contexto mexicano:

- **Reclutamiento criminal** — cárteles (CJNG, CDS, Unión Tepito) que usan chats de videojuegos y comentarios de TikTok para reclutar menores
- **Grooming sexual** — adultos que contactan y manipulan menores a través del chat en juego y redes sociales

La moderación ocurre en menos de 50ms por mensaje, sin almacenar contenido de conversaciones (cumplimiento LFPDPPP).

---

## Problema que resuelve

México tiene **18 millones de gamers menores de 18 años**. Los cárteles mexicanos han digitalizado su proceso de reclutamiento: usan videojuegos populares (Fortnite, Free Fire, Roblox) y TikTok para identificar y contactar menores vulnerables mediante códigos, emojis y slang específico del crimen organizado mexicano.

Las soluciones de moderación existentes (Perspective API, AWS Rekognition) **no conocen este contexto**:
- No identifican que `🥷🍕🆖` es una combinación de códigos del CJNG
- No entienden que "el mencho", "4L", "cuatro letras" o "chapiza" son referencias a cárteles
- No detectan patrones de grooming en español mexicano coloquial

La moderación humana cuesta 60× más y tarda horas — demasiado tarde para proteger al menor.

---

## Demo del prototipo

| Recurso | URL |
|---|---|
| **API en producción** | `https://astride-graded-paralegal.ngrok-free.dev` |
| **Documentación interactiva** | `https://astride-graded-paralegal.ngrok-free.dev/docs` |
| **Dashboard (local)** | `https://localhost:5173` tras ejecutar el proyecto |

> El dashboard se conecta al API en ngrok automáticamente. No se requiere configuración adicional para la demo.

---

## Tecnologías y herramientas utilizadas

### Backend
| Herramienta | Uso |
|---|---|
| Python 3.12 + FastAPI | API REST + WebSockets en tiempo real |
| Celery + Redis | Cola de tareas para análisis asíncrono a escala |
| SQLAlchemy + SQLite | Logs de auditoría (sin contenido de mensajes) |
| LiteLLM | Abstracción multi-proveedor LLM (waterfall automático) |

### Frontend
| Herramienta | Uso |
|---|---|
| React 19 + TypeScript | Dashboard supervisor + simulador de chat |
| Vite + mkcert | Servidor HTTPS local (requerido para acceso a micrófono) |
| Tailwind CSS | Interfaz dark-theme |
| Recharts | Gráficas de riesgo en tiempo real |

### Infraestructura
| Herramienta | Uso |
|---|---|
| Docker + docker-compose | Despliegue containerizado completo |
| ngrok | Túnel HTTPS para acceso público al API |

### Integraciones
| Herramienta | Uso |
|---|---|
| Unity SDK (C#) | Integración nativa para videojuegos Unity |
| Groq Whisper (STT) | Transcripción de voz para moderar chats de voz |
| WebSocket | Conexión en tiempo real jugadores ↔ supervisor |

---

## Documentación de herramientas de IA utilizadas

### 1. LLM — Análisis contextual de mensajes (Tier 2)

**Proveedores en cascada (waterfall):** Gemini 2.0 Flash → Cerebras Llama 3.1 → Together Llama 4 Scout → Anthropic Claude Haiku → Groq Llama 3

**¿Para qué?** Analizar mensajes ambiguos que el prefilter de reglas no puede clasificar con certeza. El LLM recibe el historial completo de conversación para detectar patrones de escalamiento gradual (grooming en 5-6 mensajes, reclutamiento con anzuelo inicial inocente).

**¿En qué medida?** Solo el ~20% de mensajes llega al LLM — el 80% restante es resuelto por el prefilter en <1ms sin costo de inferencia. El LLM responde exclusivamente en JSON estructurado con campos `risk`, `level`, `reason` y `action`.

**Prompt del sistema:** Incluye diccionario especializado de códigos de cárteles mexicanos (emojis, slang, hashtags), basado en investigación académica de Constanza Nuche *"Reclutamiento Digital"* (2024). El modelo clasifica en `block` / `warn` / `allow` con nivel `low` / `medium` / `high`.

---

### 2. Groq Whisper — Transcripción de voz (STT)

**Modelo:** `whisper-large-v3-turbo` vía API de Groq

**¿Para qué?** Transcribir fragmentos de audio del micrófono del navegador (capturados con MediaRecorder API) para extender la moderación a chats de voz. El texto transcrito pasa por el mismo pipeline de análisis que los mensajes de texto.

**¿En qué medida?** Procesa chunks de 5 segundos de audio WAV. Se usa únicamente cuando el usuario activa el micrófono voluntariamente. No se almacena el audio.

---

### 3. Sistema de reglas + prefilter (Tier 1) — sin IA externa

**¿Para qué?** Detección instantánea (<1ms) de patrones de alto riesgo conocidos sin llamadas a APIs externas: combinaciones de emojis de cártel, nombres explícitos (CJNG, el mencho, chapiza), frases de reclutamiento documentadas, solicitudes sexuales explícitas.

**Base de conocimiento:** Diccionario de ~60 patrones regex derivados de investigación sobre reclutamiento digital en México, casos de la Policía Cibernética SSPC, y análisis etnográfico de TikTok.

---

### 4. Claude (Anthropic) — Desarrollo del proyecto

**¿Para qué?** Asistencia en desarrollo de código durante el hackathon: arquitectura del sistema, implementación de endpoints, lógica de detección, debugging y optimización del prompt del sistema de moderación.

**¿En qué medida?** Herramienta de desarrollo — no forma parte del sistema en producción (excepto como fallback en el waterfall LLM si se configura la API key de Anthropic).

---

## Instrucciones para ejecutar el prototipo

### Requisitos previos
- Docker Desktop **o** Redis (`brew install redis`)
- Node.js 18+
- Python 3.11+
- API key de Groq (gratis): https://console.groq.com

### Con Docker (recomendado)

```bash
# 1. Clonar el repositorio
git clone <repo-url>
cd <repo>

# 2. Configurar variables de entorno
cp api/.env.example api/.env
# Editar api/.env y agregar: GROQ_API_KEY=gsk_...

# 3. Levantar todo
./start.sh
```

### Sin Docker

```bash
brew install redis

cp api/.env.example api/.env
# Editar api/.env y agregar: GROQ_API_KEY=gsk_...

./start-local.sh
```

### URLs locales

| Servicio | URL |
|---|---|
| Dashboard | `https://localhost:5173` |
| API REST | `http://localhost:8000` |
| Docs interactivos | `http://localhost:8000/docs` |

### Conectar Unity al API

Adjuntar `AegisSDK.cs` al GameObject y configurar:
```csharp
serverUrl = "wss://astride-graded-paralegal.ngrok-free.dev";
apiKey    = "guardiannode-dev-secret";
```

---

## Arquitectura del sistema

```
Videojuego/TikTok
      │
      ▼
  SDK / API REST
      │
      ├─ Tier 1: Prefilter regex (~0ms) ──────────────► block / warn / allow
      │          (80% de mensajes)
      │
      └─ Tier 2: LLM contextual (<50ms) ─────────────► block / warn / allow
                 (20% ambiguos)
                      │
                      ▼
              WebSocket supervisor
              Dashboard tiempo real
```

**Privacidad:** Datos efímeros — los mensajes nunca se escriben a disco. Solo se almacenan conteos agregados anonimizados (total analizado, total bloqueado, nivel de riesgo). Cumple con la Ley Federal de Protección de Datos Personales en Posesión de Particulares (LFPDPPP).

---

## Variables de entorno

```env
GROQ_API_KEY=gsk_...              # Requerida — LLM + Whisper STT
GOOGLE_API_KEY=...                # Opcional — Gemini 2.0 Flash (mejor calidad)
CEREBRAS_API_KEY=...              # Opcional — Llama 3.1 70B (más rápido)
API_KEY_SECRET=guardiannode-dev-secret
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=sqlite:///./aegis.db
```

---

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/analyze/sync` | Analiza un mensaje (síncrono, <50ms) |
| `POST` | `/analyze/social` | Analiza comentario de TikTok/Instagram |
| `POST` | `/voice/transcribe` | Transcribe audio → modera texto |
| `GET` | `/stats` | Estadísticas en tiempo real (efímeras) |
| `WS` | `/ws/game/{sala}` | Canal de chat con moderación en tiempo real |
| `WS` | `/ws/game/{sala}/supervisor` | Vista supervisor — todos los mensajes + alertas |

---

## Integrantes del equipo

| Nombre |
|---|
| Sebastián de Jesús Cruz Cruz |
| Alejandro Rodríguez Brito |
| José Emilio López Flores |
| Santiago Heriberto León Herrera |
| Eduardo Arteaga Camacho |

---

*Hackathon de Seguridad Digital Infantil · CDMX 2026*
