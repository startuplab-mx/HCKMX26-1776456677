# GuardianNode — Unity Demo (2 instances + dashboard)

Live chat between two Unity clients moderated by GuardianNode, monitored from the React dashboard.

## Architecture

```
[Unity A] ─┐
           ├─►  ws://localhost:8888/ws/game/sala-demo-unity   ──►  Moderation pipeline
[Unity B] ─┘                                                          │
                                                                      ▼
[Dashboard Supervisor] ◄── ws://localhost:8888/ws/game/sala-demo-unity/supervisor
```

Server route definitions live in `api/game_room.py`:
- `/ws/game/{room}` — players (Unity)
- `/ws/game/{room}/dashboard` — alerts only
- `/ws/game/{room}/supervisor` — full chat feed + alerts + presence

## Setup

### 1. Backend
```bash
docker compose up -d
```
API listens on `:8888`.

### 2. Unity scene
1. Create empty GameObject `GuardianClient`.
2. Add components: `GuardianNetwork`, `ChatManager`, `ChatCanvas`.
3. Build a Canvas with `TMP_InputField` (input), `Button` (send), `ScrollRect` (messages list), prefab text element with `TextMeshProUGUI`.
4. Wire references in inspector. Default `serverUrl=ws://localhost:8888`, `roomId=sala-demo-unity`.
5. Build a standalone player. Run `.app` twice (or Editor + standalone) → two Unity instances join same room.

### 3. Dashboard supervisor
```bash
cd dashboard && npm run dev
```
Open `http://localhost:5173` → click "Admin" → login → enter `roomId=sala-demo-unity` → see live chat + alerts from Unity instances.

## Message protocol (client → server)

```json
{ "type": "join",    "room": "sala-demo-unity", "player_id": "User_123", "game_id": "unity-demo" }
{ "type": "message", "text": "hola" }
```

Server → client events handled by `ChatManager.HandleNetworkMessage`: `joined`, `player_joined`, `player_left`, `message`, `blocked`, `error`.
