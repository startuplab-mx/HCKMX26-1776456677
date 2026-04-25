using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class ChatCanvas : MonoBehaviour {
    [Header("UI Refs")]
    public TMP_InputField inputField;
    public Button sendButton;
    public ScrollRect scrollView;
    public ChatManager chatManager;

    void Start() {
        if (sendButton != null) sendButton.onClick.AddListener(OnSendClicked);
        if (inputField != null) inputField.onSubmit.AddListener(_ => OnSendClicked());
    }

    void OnSendClicked() {
        if (chatManager == null || inputField == null) return;
        chatManager.SendMessage(inputField.text);
        inputField.ActivateInputField();
    }
}
