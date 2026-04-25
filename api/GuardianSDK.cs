using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using System.Text;

namespace GuardianNode
{
    [Serializable]
    public class MessagePayload
    {
        public string game_id;
        public string session_id;
        public string player_id;
        public string target_id;
        public string message;
        public string timestamp;
    }

    [Serializable]
    public class AnalysisResult
    {
        public bool risk;
        public string level;
        public string reason;
        public string action; // "allow", "warn", "block"
    }

    public class GuardianSDK : MonoBehaviour
    {
        [Header("Configuration")]
        public string apiEndpoint = "http://localhost:8888";
        public string apiKey = "guardiannode-dev-secret";
        public string gameId = "unity-game-01";

        public delegate void OnResultCallback(AnalysisResult result);

        /// <summary>
        /// Analyzes a message asynchronously.
        /// </summary>
        public void AnalyzeMessage(string playerId, string message, string targetId = "room", string sessionId = "default", OnResultCallback callback = null)
        {
            StartCoroutine(PostAnalyze(playerId, message, targetId, sessionId, callback));
        }

        private IEnumerator PostAnalyze(string playerId, string message, string targetId, string sessionId, OnResultCallback callback)
        {
            string url = $"{apiEndpoint.TrimEnd('/')}/analyze/sync";

            MessagePayload payload = new MessagePayload
            {
                game_id = gameId,
                session_id = sessionId,
                player_id = playerId,
                target_id = targetId,
                message = message,
                timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
            };

            string json = JsonUtility.ToJson(payload);
            using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
            {
                byte[] bodyRaw = Encoding.UTF8.GetBytes(json);
                request.uploadHandler = new UploadHandlerRaw(bodyRaw);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");
                request.SetRequestHeader("X-API-Key", apiKey);

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogError($"GuardianNode Error: {request.error}");
                    callback?.Invoke(CreateFallback("CONNECTION_ERROR"));
                }
                else
                {
                    try
                    {
                        AnalysisResult result = JsonUtility.FromJson<AnalysisResult>(request.downloadHandler.text);
                        callback?.Invoke(result);
                    }
                    catch (Exception e)
                    {
                        Debug.LogError($"GuardianNode Parse Error: {e.Message}");
                        callback?.Invoke(CreateFallback("PARSE_ERROR"));
                    }
                }
            }
        }

        private AnalysisResult CreateFallback(string reason)
        {
            return new AnalysisResult
            {
                risk = true,
                level = "medium",
                reason = $"SDK_FALLBACK: {reason}",
                action = "warn"
            };
        }
    }
}
