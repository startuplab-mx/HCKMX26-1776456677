using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace GuardianNode
{
    [Serializable]
    public class STTResponse
    {
        // Esto asume una respuesta simplificada tipo Deepgram o Whisper
        public string transcript;
    }

    [RequireComponent(typeof(GuardianSDK))]
    public class GuardianAudioModerator : MonoBehaviour
    {
        [Header("STT Configuration (ej. Deepgram)")]
        public string sttEndpoint = "https://api.deepgram.com/v1/listen";
        public string sttApiKey = "TU_DEEPGRAM_API_KEY";

        [Header("Audio Settings")]
        public int recordDurationSec = 5;
        private string micName;
        private AudioClip recordingClip;

        private GuardianSDK guardian;
        private string currentPlayerId = "PlayerVoice_123";

        void Start()
        {
            guardian = GetComponent<GuardianSDK>();
            
            // Iniciar micrófono predeterminado
            if (Microphone.devices.Length > 0)
            {
                micName = Microphone.devices[0];
                Debug.Log($"[Guardian Audio] Usando micrófono: {micName}");
                StartRecordingChunk();
            }
            else
            {
                Debug.LogError("[Guardian Audio] No se detectó ningún micrófono.");
            }
        }

        private void StartRecordingChunk()
        {
            // Graba un fragmento (chunk) de audio
            recordingClip = Microphone.Start(micName, false, recordDurationSec, 16000);
            StartCoroutine(ProcessChunkAfterDelay());
        }

        private IEnumerator ProcessChunkAfterDelay()
        {
            // Esperar a que termine de grabar el fragmento
            yield return new WaitForSeconds(recordDurationSec);
            Microphone.End(micName);

            // 1. Obtener el .WAV del audio
            byte[] audioBytes = WavUtility.FromAudioClip(recordingClip);

            if (audioBytes != null && audioBytes.Length > 0)
            {
                // 2. Enviar a Speech-to-Text (Transcribir)
                yield return StartCoroutine(TranscribeAudioAndModerate(audioBytes));
            }

            // Repetir el ciclo (grabar el siguiente fragmento)
            StartRecordingChunk();
        }

        private IEnumerator TranscribeAudioAndModerate(byte[] audioBytes)
        {
            Debug.Log("[Guardian Audio] Enviando chunk de audio a Speech-to-Text...");

            using (UnityWebRequest request = new UnityWebRequest(sttEndpoint, "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(audioBytes);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "audio/wav");
                request.SetRequestHeader("Authorization", $"Token {sttApiKey}");

                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning($"[Guardian Audio] Error STT: {request.error}");
                }
                else
                {
                    // 3. Analizar la respuesta del STT
                    string jsonResult = request.downloadHandler.text;
                    string transcript = ParseTranscript(jsonResult);

                    if (!string.IsNullOrEmpty(transcript))
                    {
                        Debug.Log($"[Guardian Audio] Transcripción exitosa: '{transcript}'");

                        // 4. EL PASO MÁGICO: Enviar el texto transcrito a GuardianNode para moderación
                        guardian.AnalyzeMessage(currentPlayerId, transcript, callback: OnModerationResult);
                    }
                }
            }
        }

        private string ParseTranscript(string jsonResult)
        {
            // Aquí extraes el texto dependiendo de qué API uses (Deepgram, Whisper, etc.)
            // Este es un ejemplo genérico asumiendo un JSON simple {"transcript": "hola"}
            try
            {
                STTResponse res = JsonUtility.FromJson<STTResponse>(jsonResult);
                return res.transcript;
            }
            catch
            {
                // Regex fallback super simple por si el JSON es complejo
                var match = System.Text.RegularExpressions.Regex.Match(jsonResult, @"""transcript"":\s*""([^""]+)""");
                if (match.Success) return match.Groups[1].Value;
                return "";
            }
        }

        private void OnModerationResult(AnalysisResult result)
        {
            if (result.action == "block")
            {
                Debug.LogError($"[Guardian Audio] 🚨 MUTEANDO JUGADOR! Razón: {result.reason} (Riesgo: {result.level})");
                // Aquí pondrías la lógica de tu juego para silenciar el Voice Chat (ej. Vivox.MutePlayer)
            }
            else if (result.action == "warn")
            {
                Debug.LogWarning($"[Guardian Audio] ⚠️ Advertencia de voz: {result.reason}");
            }
            else
            {
                Debug.Log("[Guardian Audio] ✅ Voz limpia.");
            }
        }
    }

    /// <summary>
    /// Utilidad simple para convertir AudioClip a formato WAV compatible con APIs REST.
    /// </summary>
    public static class WavUtility
    {
        public static byte[] FromAudioClip(AudioClip clip)
        {
            if (clip == null) return null;
            var samples = new float[clip.samples];
            clip.GetData(samples, 0);
            Int16[] intData = new Int16[samples.Length];
            Byte[] bytesData = new Byte[samples.Length * 2];
            int rescaleFactor = 32767;
            for (int i = 0; i < samples.Length; i++)
            {
                intData[i] = (short)(samples[i] * rescaleFactor);
                Byte[] byteArr = new Byte[2];
                byteArr = BitConverter.GetBytes(intData[i]);
                byteArr.CopyTo(bytesData, i * 2);
            }
            
            // Header WAV básico
            var stream = new System.IO.MemoryStream();
            var writer = new System.IO.BinaryWriter(stream);
            writer.Write("RIFF".ToCharArray());
            writer.Write(36 + bytesData.Length);
            writer.Write("WAVE".ToCharArray());
            writer.Write("fmt ".ToCharArray());
            writer.Write(16);
            writer.Write((short)1);
            writer.Write((short)clip.channels);
            writer.Write(clip.frequency);
            writer.Write(clip.frequency * clip.channels * 2);
            writer.Write((short)(clip.channels * 2));
            writer.Write((short)16);
            writer.Write("data".ToCharArray());
            writer.Write(bytesData.Length);
            writer.Write(bytesData);
            return stream.ToArray();
        }
    }
}
