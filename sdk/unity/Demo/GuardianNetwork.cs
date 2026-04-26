using System;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;
using UnityEngine;

[Serializable]
class JoinPayload {
    public string type = "join";
    public string room;
    public string player_id;
    public string game_id;
}

[Serializable]
class TextPayload {
    public string type = "message";
    public string text;
}

public class GuardianNetwork : MonoBehaviour {
    [Header("Server")]
    public string serverUrl = "ws://localhost:8000";
    public string roomId = "sala-demo-unity";
    public string gameId = "unity-demo";
    public string playerId = "";

    private ClientWebSocket websocket;
    private ChatManager chatManager;
    private readonly Queue<string> messageQueue = new Queue<string>();
    private CancellationTokenSource cts;

    async void Start() {
        chatManager = GetComponent<ChatManager>();
        if (string.IsNullOrEmpty(playerId))
            playerId = "User_" + UnityEngine.Random.Range(100, 999);
        cts = new CancellationTokenSource();
        await Connect();
    }

    void Update() {
        lock (messageQueue) {
            while (messageQueue.Count > 0) {
                string msg = messageQueue.Dequeue();
                chatManager?.HandleNetworkMessage(msg);
            }
        }
    }

    async Task Connect() {
        websocket = new ClientWebSocket();
        try {
            string url = $"{serverUrl.TrimEnd('/')}/ws/game/{roomId}";
            await websocket.ConnectAsync(new Uri(url), cts.Token);
            var join = new JoinPayload { room = roomId, player_id = playerId, game_id = gameId };
            await SendRaw(JsonUtility.ToJson(join));
            _ = ReceiveLoop();
        } catch (Exception e) {
            Debug.LogError("[Network] Connect error: " + e.Message);
        }
    }

    async Task ReceiveLoop() {
        var buffer = new byte[1024 * 8];
        var ms = new System.IO.MemoryStream();
        try {
            while (websocket.State == WebSocketState.Open) {
                ms.SetLength(0);
                WebSocketReceiveResult result;
                do {
                    result = await websocket.ReceiveAsync(new ArraySegment<byte>(buffer), cts.Token);
                    ms.Write(buffer, 0, result.Count);
                } while (!result.EndOfMessage);

                string json = Encoding.UTF8.GetString(ms.ToArray());
                lock (messageQueue) { messageQueue.Enqueue(json); }
            }
        } catch (Exception e) {
            Debug.LogWarning("[Network] Receive ended: " + e.Message);
        }
    }

    public async Task SendChatMessage(string text) {
        if (websocket == null || websocket.State != WebSocketState.Open) return;
        var payload = new TextPayload { text = text };
        await SendRaw(JsonUtility.ToJson(payload));
    }

    private async Task SendRaw(string data) {
        var buffer = Encoding.UTF8.GetBytes(data);
        await websocket.SendAsync(new ArraySegment<byte>(buffer), WebSocketMessageType.Text, true, cts.Token);
    }

    async void OnDestroy() {
        cts?.Cancel();
        if (websocket != null && websocket.State == WebSocketState.Open) {
            try { await websocket.CloseAsync(WebSocketCloseStatus.NormalClosure, "bye", CancellationToken.None); }
            catch { }
        }
    }
}
