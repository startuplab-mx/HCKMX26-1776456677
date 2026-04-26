import { useEffect, useRef, useState, useCallback } from 'react'
import { Send, Shield, ShieldAlert, ShieldX, Wifi, WifiOff, Users, Bot, Square, Mic, MicOff, Loader } from 'lucide-react'
import type { ChatMessage, RiskLevel } from '../types'

interface Props {
  messages: ChatMessage[]
  status: string
  players: string[]
  playerId?: string
  onSend: (text: string) => void
  serverUrl?: string
  apiKey?: string
}

// Minecraft-style name colors for players
const PLAYER_COLORS = [
  'text-green-400', 'text-blue-400', 'text-yellow-400',
  'text-purple-400', 'text-cyan-400', 'text-orange-400',
]

// Secuencia de reclutamiento para demo automática (escalamiento gradual)
const DEMO_SCRIPT = [
  { delay: 0,     text: 'gg bro, nice shot!' },
  { delay: 2500,  text: 'oye eres muy bueno, cuánto tiempo llevas jugando?' },
  { delay: 5500,  text: 'cuántos años tienes? yo tengo 16' },
  { delay: 9000,  text: 'te puedo conseguir skins gratis si me ayudas con algo pequeño' },
  { delay: 13000, text: 'conozco un trabajo fácil, te pagan bien y rápido' },
  { delay: 17000, text: 'pásate a mi discord privado para hablar mejor' },
  { delay: 20500, text: 'no le digas a nadie, esto es entre nosotros' },
]

// Quick test phrases that simulate real recruitment patterns
const QUICK_PHRASES = [
  { label: 'Normal', text: 'gg bro, nice shot!', safe: true },
  { label: 'Anzuelo', text: 'eres muy bueno, llevas mucho jugando?', safe: true },
  { label: 'Sondeo', text: 'cuántos años tienes? yo tengo 14', safe: false },
  { label: 'Oferta', text: 'oye te puedo conseguir skins gratis si me ayudas con algo', safe: false },
  { label: 'Migrar', text: 'pásate a mi discord privado para hablar mejor', safe: false },
  { label: 'Dinero', text: 'conozco un trabajo fácil, te pagan bien y rápido', safe: false },
  { label: 'Secreto', text: 'no le digas a nadie, esto es entre nosotros', safe: false },
  { label: 'Ubicación', text: 'dónde vives? yo soy de guadalajara', safe: false },
]

export function ChatPanel({ messages, status, players, onSend, serverUrl, apiKey }: Props) {
  const [input, setInput] = useState('')
  const [demoRunning, setDemoRunning] = useState(false)
  const demoTimers = useRef<ReturnType<typeof setTimeout>[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  // Voice recording state
  const [micPerm, setMicPerm] = useState<'unknown' | 'requesting' | 'granted' | 'denied'>('unknown')
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [voiceError, setVoiceError] = useState('')
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)

  // Check permission on mount
  useEffect(() => {
    if (!serverUrl) return
    navigator.permissions?.query({ name: 'microphone' as PermissionName })
      .then(p => {
        setMicPerm(p.state === 'granted' ? 'granted' : p.state === 'denied' ? 'denied' : 'unknown')
        p.onchange = () => setMicPerm(p.state === 'granted' ? 'granted' : p.state === 'denied' ? 'denied' : 'unknown')
      })
      .catch(() => setMicPerm('unknown'))
  }, [serverUrl])

  const requestMicPermission = useCallback(async () => {
    setMicPerm('requesting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach(t => t.stop())
      setMicPerm('granted')
    } catch {
      setMicPerm('denied')
    }
  }, [])

  const startRecording = useCallback(async () => {
    if (!serverUrl || !apiKey) return
    setVoiceError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      setMicPerm('granted')
      streamRef.current = stream
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/ogg'
      const mr = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = async () => {
        streamRef.current?.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: mimeType })
        setTranscribing(true)
        try {
          const form = new FormData()
          form.append('audio', blob, mimeType === 'audio/webm' ? 'voice.webm' : 'voice.ogg')
          const base = serverUrl.replace(/^ws/, 'http')
          const res = await fetch(`${base}/voice/transcribe`, {
            method: 'POST',
            headers: { 'X-API-Key': apiKey },
            body: form,
          })
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          const { transcript } = await res.json()
          if (transcript) onSend(transcript)
        } catch {
          setVoiceError('Error de transcripción')
          setTimeout(() => setVoiceError(''), 3000)
        } finally {
          setTranscribing(false)
        }
      }
      mr.start()
      mediaRecorderRef.current = mr
      setRecording(true)
    } catch (e: unknown) {
      const name = (e as { name?: string })?.name
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setMicPerm('denied')
      } else {
        setVoiceError('Error al iniciar micrófono')
        setTimeout(() => setVoiceError(''), 3000)
      }
    }
  }, [serverUrl, apiKey, onSend])

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop()
    setRecording(false)
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = () => {
    const t = input.trim()
    if (!t) return
    onSend(t)
    setInput('')
  }

  const startDemo = useCallback(() => {
    if (demoRunning || status !== 'connected') return
    setDemoRunning(true)
    demoTimers.current = DEMO_SCRIPT.map(({ delay, text }) =>
      setTimeout(() => onSend(text), delay)
    )
    // auto-stop after last message
    const last = DEMO_SCRIPT[DEMO_SCRIPT.length - 1]
    demoTimers.current.push(setTimeout(() => setDemoRunning(false), last.delay + 1000))
  }, [demoRunning, status, onSend])

  const stopDemo = useCallback(() => {
    demoTimers.current.forEach(clearTimeout)
    demoTimers.current = []
    setDemoRunning(false)
  }, [])

  useEffect(() => () => demoTimers.current.forEach(clearTimeout), [])

  const playerColor = (pid: string) => {
    const idx = players.indexOf(pid) % PLAYER_COLORS.length
    return PLAYER_COLORS[Math.max(0, idx)]
  }

  return (
    <div className="flex flex-col h-full bg-[#111118] border-r border-gray-800">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-[#0d0d14]">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_6px_#22c55e]" />
          <span className="text-sm font-mono text-green-400 font-semibold">GUARDIAN</span>
          <span className="text-xs text-gray-600 font-mono">CHAT SIMULATOR</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <Users size={12} />
            <span>{players.length}/2</span>
          </div>
          <button
            onClick={demoRunning ? stopDemo : startDemo}
            disabled={status !== 'connected'}
            title={demoRunning ? 'Detener demo' : 'Ejecutar secuencia de reclutamiento automática'}
            className={`flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              demoRunning
                ? 'border-red-700 text-red-400 bg-red-950/40 hover:border-red-500'
                : 'border-purple-700 text-purple-400 bg-purple-950/30 hover:border-purple-500'
            }`}
          >
            {demoRunning ? <><Square size={9} /> STOP</> : <><Bot size={10} /> DEMO</>}
          </button>
          <StatusBadge status={status} />
        </div>
      </div>

      {/* Quick phrases */}
      <div className="flex gap-1.5 px-3 py-2 border-b border-gray-800 overflow-x-auto scrollbar-thin">
        {QUICK_PHRASES.map(p => (
          <button
            key={p.label}
            onClick={() => onSend(p.text)}
            className={`shrink-0 text-xs px-2 py-1 rounded border font-mono transition-colors ${
              p.safe
                ? 'border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200'
                : 'border-red-900/60 text-red-400/80 hover:border-red-500 hover:text-red-300'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1 font-mono text-sm">
        {messages.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-600 text-xs">
            Esperando mensajes...
          </div>
        )}
        {messages.map(msg => (
          <MessageRow
            key={msg.id}
            msg={msg}
            isSelf={msg.self}
            nameColor={msg.from === 'SISTEMA' || msg.from === 'ERROR' ? 'text-gray-500' : playerColor(msg.from)}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Players online */}
      {players.length > 0 && (
        <div className="px-3 py-1.5 border-t border-gray-800 flex gap-2">
          {players.map((p, i) => (
            <span key={p} className={`text-xs font-mono ${PLAYER_COLORS[i % PLAYER_COLORS.length]}`}>
              ● {p}
            </span>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-3 py-3 border-t border-gray-800 bg-[#0d0d14]">
        {voiceError && (
          <p className="text-xs text-red-400 font-mono mb-1.5 px-1">{voiceError}</p>
        )}
        <div className="flex gap-2">
          <input
            value={transcribing ? '' : input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send()}
            placeholder={
              transcribing ? 'Transcribiendo...' :
              recording ? '🔴 Grabando voz...' :
              status === 'connected' ? 'Escribe un mensaje...' : 'Conectando...'
            }
            disabled={status !== 'connected' || recording || transcribing}
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-green-600 disabled:opacity-40 font-mono"
          />
          {serverUrl && micPerm === 'denied' && (
            <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-red-950/60 border border-red-800/60 text-red-400 text-[10px] font-mono">
              <MicOff size={12} />
              <span>Bloqueado</span>
            </div>
          )}
          {serverUrl && micPerm === 'unknown' && (
            <button
              onClick={requestMicPermission}
              disabled={status !== 'connected'}
              title="Permitir acceso al micrófono para voz"
              className="flex items-center gap-1.5 px-2 py-2 rounded-lg bg-blue-900/40 border border-blue-700/60 text-blue-300 hover:bg-blue-900/70 transition-colors disabled:opacity-40 text-[10px] font-mono"
            >
              <Mic size={14} />
              <span>Permitir mic</span>
            </button>
          )}
          {serverUrl && micPerm === 'requesting' && (
            <div className="flex items-center gap-1.5 px-2 py-2 rounded-lg bg-yellow-950/40 border border-yellow-800/60 text-yellow-400 text-[10px] font-mono">
              <Loader size={14} className="animate-spin" />
              <span>Solicitando...</span>
            </div>
          )}
          {serverUrl && micPerm === 'granted' && (
            <button
              onClick={recording ? stopRecording : startRecording}
              disabled={status !== 'connected' || transcribing}
              title={recording ? 'Detener grabación' : 'Grabar mensaje de voz'}
              className={`px-3 py-2 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                recording
                  ? 'bg-red-600 hover:bg-red-500 text-white animate-pulse'
                  : transcribing
                  ? 'bg-gray-700 text-gray-400'
                  : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
              }`}
            >
              {transcribing ? <Loader size={16} className="animate-spin" /> :
               recording ? <MicOff size={16} /> : <Mic size={16} />}
            </button>
          )}
          <button
            onClick={send}
            disabled={status !== 'connected' || recording || transcribing}
            className="bg-green-600 hover:bg-green-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-3 py-2 rounded-lg transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}

function MessageRow({ msg, isSelf, nameColor }: { msg: ChatMessage; isSelf: boolean; nameColor: string }) {
  const isSystem = msg.from === 'SISTEMA' || msg.from === 'ERROR'

  if (isSystem) {
    return (
      <div className="text-center">
        <span className="text-xs text-gray-600 italic">{msg.text}</span>
      </div>
    )
  }

  return (
    <div className={`msg-enter flex gap-2 items-start group ${isSelf ? 'flex-row-reverse' : ''}`}>
      <RiskIcon level={msg.level} blocked={msg.blocked} />
      <div className={`max-w-[75%] ${isSelf ? 'items-end' : 'items-start'} flex flex-col gap-0.5`}>
        <span className={`text-xs ${nameColor} font-semibold`}>{msg.from}</span>
        <div className={`rounded-lg px-3 py-1.5 text-sm leading-relaxed ${
          msg.blocked
            ? 'bg-red-950/60 border border-red-800/60 text-red-300 line-through opacity-70'
            : msg.warned
            ? 'bg-yellow-950/40 border border-yellow-800/40 text-yellow-100'
            : isSelf
            ? 'bg-green-900/30 border border-green-800/30 text-green-100'
            : 'bg-gray-800/60 border border-gray-700/40 text-gray-200'
        }`}>
          {msg.blocked && (
            <span className="block text-xs text-red-400 mb-1 no-underline font-semibold not-italic">
              [MENSAJE BLOQUEADO]
            </span>
          )}
          {msg.text}
          {msg.warned && msg.reason && (
            <span className="block text-xs text-yellow-500/80 mt-1">⚠ {msg.reason}</span>
          )}
          {msg.blocked && msg.reason && (
            <span className="block text-xs text-red-400/80 mt-1 no-underline">🛡 {msg.reason}</span>
          )}
        </div>
        <span className="text-[10px] text-gray-700 px-1">
          {msg.ts.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </span>
      </div>
    </div>
  )
}

function RiskIcon({ level, blocked }: { level: RiskLevel; blocked: boolean }) {
  if (blocked) return <ShieldX size={14} className="text-red-500 mt-1 shrink-0" />
  if (level === 'high') return <ShieldAlert size={14} className="text-red-400 mt-1 shrink-0" />
  if (level === 'medium') return <Shield size={14} className="text-yellow-400 mt-1 shrink-0" />
  return <Shield size={14} className="text-gray-700 mt-1 shrink-0" />
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
    connected:    { icon: <Wifi size={11} />,    color: 'text-green-400 border-green-800 bg-green-950/40', label: 'EN LÍNEA' },
    connecting:   { icon: <Wifi size={11} />,    color: 'text-yellow-400 border-yellow-800 bg-yellow-950/40', label: 'CONECTANDO' },
    disconnected: { icon: <WifiOff size={11} />, color: 'text-gray-500 border-gray-700 bg-gray-900', label: 'OFFLINE' },
    error:        { icon: <WifiOff size={11} />, color: 'text-red-400 border-red-800 bg-red-950/40', label: 'ERROR' },
  }
  const s = map[status] ?? map.disconnected
  return (
    <span className={`flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded border ${s.color}`}>
      {s.icon} {s.label}
    </span>
  )
}
