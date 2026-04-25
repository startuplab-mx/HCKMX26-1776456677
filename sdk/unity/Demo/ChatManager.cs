using UnityEngine;
using TMPro;

[System.Serializable]
public class NetMessage {
    public string type;
    public string from;
    public string text;
    public bool blocked;
    public bool warned;
    public string level;
    public string reason;
    public string player_id;
    public string detail;
}

public class ChatManager : MonoBehaviour {
    [Header("UI Refs")]
    public TMP_InputField inputField;
    public Transform chatContent;
    public GameObject textPrefab;

    [Header("Network")]
    public GuardianNetwork network;

    public async void SendMessage(string text) {
        if (string.IsNullOrEmpty(text)) return;
        if (network != null) await network.SendChatMessage(text);
        if (inputField != null) inputField.text = "";
    }

    public void HandleNetworkMessage(string json) {
        try {
            NetMessage msg = JsonUtility.FromJson<NetMessage>(json);
            if (msg == null || string.IsNullOrEmpty(msg.type)) return;

            switch (msg.type) {
                case "message":
                    if (msg.blocked) AddMessageToUI($"<color=red>[BLOQUEADO]</color> <i>{msg.from}</i>");
                    else if (msg.warned) AddMessageToUI($"<color=yellow>[!]</color> <b>{msg.from}:</b> {msg.text}");
                    else AddMessageToUI($"<b>{msg.from}:</b> {msg.text}");
                    break;
                case "blocked":
                    AddMessageToUI($"<color=red>[TU MENSAJE BLOQUEADO] {msg.reason}</color>");
                    break;
                case "joined":
                    AddMessageToUI("<color=grey><i>Conectado a la sala</i></color>");
                    break;
                case "player_joined":
                    AddMessageToUI($"<color=grey><i>{msg.player_id} entró</i></color>");
                    break;
                case "player_left":
                    AddMessageToUI($"<color=grey><i>{msg.player_id} salió</i></color>");
                    break;
                case "error":
                    AddMessageToUI($"<color=orange><i>Error: {msg.detail}</i></color>");
                    break;
            }
        } catch (System.Exception e) {
            Debug.LogWarning("[Chat] parse fail: " + e.Message + " raw=" + json);
        }
    }

    private void AddMessageToUI(string msg) {
        if (textPrefab == null || chatContent == null) {
            Debug.Log("[Chat] " + msg);
            return;
        }
        GameObject newText = Instantiate(textPrefab, chatContent);
        newText.GetComponent<TextMeshProUGUI>().text = msg;
        Canvas.ForceUpdateCanvases();
    }
}
