// AEGIS Unity SDK v1.0
// Requires: NativeWebSocket (https://github.com/endel/NativeWebSocket)
// Add via Package Manager → Add from git URL:
//   https://github.com/endel/NativeWebSocket.git#upm
//
// Also add Newtonsoft.Json:
//   https://github.com/applejag/Newtonsoft.Json-for-Unity

using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using NativeWebSocket;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Events;

namespace AEGIS
{
    // ── Models ────────────────────────────────────────────────────────────────

    public enum RiskLevel { low, medium, high }
    public enum RiskAction { allow, warn, block }

    [Serializable]
    public class AnalysisResult
    {
        public bool      risk;
        public RiskLevel level;
        public string    reason;
        public RiskAction action;
    }

    [Serializable]
    public class ChatMessage
    {
        public string    from;
        public string    text;
        public RiskLevel level;
        public bool      warned;
        public bool      blocked;
        public string    reason;
    }

    [Serializable]
    public class AlertEvent
    {
        public RiskLevel  level;
        public string     reason;
        public RiskAction action;
        public string     from;
        public string     text;
    }

    // ── Events ────────────────────────────────────────────────────────────────

    [Serializable] public class MessageEvent  : UnityEvent<ChatMessage>  { }
    [Serializable] public class AlertEvt      : UnityEvent<AlertEvent>   { }
    [Serializable] public class StringEvent   : UnityEvent<string>       { }
    [Serializable] public class ConnectEvent  : UnityEvent               { }

    // ── SDK Component ─────────────────────────────────────────────────────────

    /// <summary>
    /// Drop this component on any GameObject to add AEGIS chat moderation.
    /// Wire events in the Inspector or subscribe in code.
    /// </summary>
    public class AEGISSDK : MonoBehaviour
    {
        [Header("Server")]
        public string serverUrl = "ws://localhost:8000";
        public string apiKey    = "aegis-dev-secret";

        [Header("Room")]
        public string roomId   = "unity-room";
        public string playerId = "Player1";
        public string gameId   = "UnityGame";

        [Header("Options")]
        public bool autoReconnect    = true;
        public float reconnectDelay  = 3f;

        [Header("Events")]
        public MessageEvent  OnMessage;
        public AlertEvt      OnAlert;
        public MessageEvent  OnBlocked;
        public StringEvent   OnPlayerJoined;
        public StringEvent   OnPlayerLeft;
        public ConnectEvent  OnConnected;
        public ConnectEvent  OnDisconnected;

        WebSocket _ws;
        bool      _connected;
        float     _reconnectTimer;
        bool      _shouldReconnect;

        public bool  IsConnected => _connected;
        public string PlayerId   => playerId;

        // ── Lifecycle ──────────────────────────────────────────────────────────

        async void Start() => await Connect();

        void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            _ws?.DispatchMessageQueue();
#endif
            if (_shouldReconnect && autoReconnect)
            {
                _reconnectTimer -= Time.deltaTime;
                if (_reconnectTimer <= 0)
                {
                    _shouldReconnect = false;
                    _ = Connect();
                }
            }
        }

        async void OnDestroy() => await Disconnect();

        // ── Public API ─────────────────────────────────────────────────────────

        public async Task Connect()
        {
            if (_ws != null) return;

            string url = $"{serverUrl}/ws/game/{roomId}";
            _ws = new WebSocket(url);

            _ws.OnOpen += HandleOpen;
            _ws.OnMessage += HandleMessage;
            _ws.OnError += HandleError;
            _ws.OnClose += HandleClose;

            await _ws.Connect();
        }

        public async Task Disconnect()
        {
            autoReconnect = false;
            if (_ws != null)
            {
                await _ws.Close();
                _ws = null;
            }
        }

        /// <summary>Send a chat message. AEGIS analyzes it server-side.</summary>
        public void SendMessage(string text)
        {
            if (!_connected)
            {
                Debug.LogWarning("[AEGIS] Not connected");
                return;
            }
            var payload = new { type = "message", text };
            _ws.SendText(JsonConvert.SerializeObject(payload));
        }

        // ── Handlers ───────────────────────────────────────────────────────────

        void HandleOpen()
        {
            var join = new { type = "join", player_id = playerId, game_id = gameId };
            _ws.SendText(JsonConvert.SerializeObject(join));
        }

        void HandleMessage(byte[] bytes)
        {
            string raw = System.Text.Encoding.UTF8.GetString(bytes);
            JObject data;
            try { data = JObject.Parse(raw); }
            catch { return; }

            string type = data["type"]?.ToString();

            switch (type)
            {
                case "joined":
                    _connected = true;
                    OnConnected?.Invoke();
                    Debug.Log($"[AEGIS] Connected to room '{roomId}' as '{playerId}'");
                    break;

                case "player_joined":
                    OnPlayerJoined?.Invoke(data["player_id"]?.ToString());
                    break;

                case "player_left":
                    OnPlayerLeft?.Invoke(data["player_id"]?.ToString());
                    break;

                case "message":
                    var msg = new ChatMessage
                    {
                        from    = data["from"]?.ToString(),
                        text    = data["text"]?.ToString(),
                        level   = ParseLevel(data["level"]?.ToString()),
                        warned  = data["warned"]?.ToObject<bool>() ?? false,
                        blocked = false,
                        reason  = data["reason"]?.ToString() ?? "",
                    };
                    OnMessage?.Invoke(msg);

                    if (msg.warned)
                    {
                        var alert = new AlertEvent
                        {
                            level  = msg.level,
                            reason = msg.reason,
                            action = RiskAction.warn,
                            from   = msg.from,
                            text   = msg.text,
                        };
                        OnAlert?.Invoke(alert);
                    }
                    break;

                case "blocked":
                    var blocked = new ChatMessage
                    {
                        from    = playerId,
                        text    = data["text"]?.ToString(),
                        level   = ParseLevel(data["level"]?.ToString()),
                        warned  = false,
                        blocked = true,
                        reason  = data["reason"]?.ToString() ?? "",
                    };
                    OnBlocked?.Invoke(blocked);
                    OnAlert?.Invoke(new AlertEvent
                    {
                        level  = blocked.level,
                        reason = blocked.reason,
                        action = RiskAction.block,
                        from   = playerId,
                        text   = blocked.text,
                    });
                    Debug.LogWarning($"[AEGIS] Message BLOCKED: {blocked.reason}");
                    break;

                case "alert":
                    OnAlert?.Invoke(new AlertEvent
                    {
                        level  = ParseLevel(data["level"]?.ToString()),
                        reason = data["reason"]?.ToString() ?? "",
                        action = ParseAction(data["action"]?.ToString()),
                        from   = data["from"]?.ToString() ?? "",
                        text   = data["text"]?.ToString() ?? "",
                    });
                    break;

                case "error":
                    Debug.LogError($"[AEGIS] Server error: {data["detail"]}");
                    break;
            }
        }

        void HandleError(string error)
        {
            _connected = false;
            Debug.LogError($"[AEGIS] WebSocket error: {error}");
        }

        void HandleClose(WebSocketCloseCode code)
        {
            _connected = false;
            _ws = null;
            OnDisconnected?.Invoke();
            Debug.Log($"[AEGIS] Disconnected ({code})");

            if (autoReconnect)
            {
                _shouldReconnect = true;
                _reconnectTimer  = reconnectDelay;
            }
        }

        // ── Helpers ────────────────────────────────────────────────────────────

        static RiskLevel ParseLevel(string s) => s switch
        {
            "high"   => RiskLevel.high,
            "medium" => RiskLevel.medium,
            _        => RiskLevel.low,
        };

        static RiskAction ParseAction(string s) => s switch
        {
            "block" => RiskAction.block,
            "warn"  => RiskAction.warn,
            _       => RiskAction.allow,
        };
    }

    // ── REST Client (for non-realtime use) ────────────────────────────────────

    /// <summary>
    /// One-shot HTTP analysis. Use when you don't need a persistent room connection.
    /// Call from a coroutine or async method.
    /// </summary>
    public static class AEGISHttp
    {
        public static async Task<AnalysisResult> Analyze(
            string serverUrl,
            string apiKey,
            string message,
            string playerId,
            string targetId,
            string gameId    = "UnityGame",
            string sessionId = "default")
        {
            var payload = new
            {
                message,
                player_id  = playerId,
                target_id  = targetId,
                game_id    = gameId,
                session_id = sessionId,
            };

            using var client = new System.Net.Http.HttpClient();
            client.DefaultRequestHeaders.Add("X-API-Key", apiKey);

            var content = new System.Net.Http.StringContent(
                JsonConvert.SerializeObject(payload),
                System.Text.Encoding.UTF8,
                "application/json"
            );

            var resp = await client.PostAsync($"{serverUrl}/analyze/sync", content);
            resp.EnsureSuccessStatusCode();

            string body = await resp.Content.ReadAsStringAsync();
            var data = JObject.Parse(body);

            return new AnalysisResult
            {
                risk   = data["risk"]?.ToObject<bool>() ?? false,
                level  = AEGISSDK_ParseLevel(data["level"]?.ToString()),
                reason = data["reason"]?.ToString() ?? "",
                action = AEGISSDK_ParseAction(data["action"]?.ToString()),
            };
        }

        static RiskLevel AEGISSDK_ParseLevel(string s) => s switch
        {
            "high"   => RiskLevel.high,
            "medium" => RiskLevel.medium,
            _        => RiskLevel.low,
        };

        static RiskAction AEGISSDK_ParseAction(string s) => s switch
        {
            "block" => RiskAction.block,
            "warn"  => RiskAction.warn,
            _       => RiskAction.allow,
        };
    }
}
