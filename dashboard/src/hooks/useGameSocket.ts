import { useEffect, useRef, useState, useCallback } from 'react'
import type { ChatMessage, RiskLevel } from '../types'

type SocketStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

// Works on HTTP (no secure context needed)
function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

interface UseGameSocketOptions {
  serverUrl: string
  roomId: string
  playerId: string
  gameId: string
  onAlert?: (alert: object) => void
}

export function useGameSocket({ serverUrl, roomId, playerId, gameId, onAlert }: UseGameSocketOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [status, setStatus] = useState<SocketStatus>('disconnected')
  const [players, setPlayers] = useState<string[]>([])
  const ws = useRef<WebSocket | null>(null)
  const onAlertRef = useRef(onAlert)
  onAlertRef.current = onAlert

  const addMessage = useCallback((msg: Omit<ChatMessage, 'id' | 'ts'>) => {
    setMessages(prev => [...prev, { ...msg, id: uuid(), ts: new Date() }])
  }, [])

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return
    if (ws.current?.readyState === WebSocket.CONNECTING) return

    const url = `${serverUrl}/ws/game/${roomId}`
    setStatus('connecting')
    const socket = new WebSocket(url)
    ws.current = socket

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'join', room: roomId, player_id: playerId, game_id: gameId }))
    }

    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      switch (msg.type) {
        case 'joined':
          setStatus('connected')
          setPlayers(msg.players)
          addMessage({ from: 'SISTEMA', text: `Conectado a sala ${msg.room} como ${msg.player_id}`, level: 'low', blocked: false, warned: false, reason: '', self: false })
          break
        case 'player_joined':
          setPlayers(prev => [...new Set([...prev, msg.player_id])])
          addMessage({ from: 'SISTEMA', text: `${msg.player_id} entró a la sala`, level: 'low', blocked: false, warned: false, reason: '', self: false })
          break
        case 'player_left':
          setPlayers(prev => prev.filter(p => p !== msg.player_id))
          addMessage({ from: 'SISTEMA', text: `${msg.player_id} salió de la sala`, level: 'low', blocked: false, warned: false, reason: '', self: false })
          break
        case 'message':
          addMessage({ from: msg.from, text: msg.text, level: msg.level as RiskLevel, blocked: false, warned: msg.warned, reason: msg.reason, self: msg.from === playerId })
          break
        case 'blocked':
          addMessage({ from: playerId, text: msg.text, level: msg.level as RiskLevel, blocked: true, warned: false, reason: msg.reason, self: true })
          onAlertRef.current?.({ type: 'alert', level: msg.level, reason: msg.reason, from: playerId, text: msg.text, action: 'block' })
          break
        case 'alert':
          onAlertRef.current?.(msg)
          break
        case 'error':
          addMessage({ from: 'ERROR', text: msg.detail, level: 'high', blocked: false, warned: false, reason: '', self: false })
          break
      }
    }

    socket.onerror = () => setStatus('error')
    socket.onclose = () => { setStatus('disconnected'); setPlayers([]) }
  }, [serverUrl, roomId, playerId, gameId, addMessage])

  const sendMessage = useCallback((text: string) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'message', text }))
    }
  }, [])

  const disconnect = useCallback(() => {
    ws.current?.close()
    ws.current = null
  }, [])

  useEffect(() => {
    const id = setInterval(() => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 20000)
    return () => clearInterval(id)
  }, [])

  return { messages, status, players, connect, disconnect, sendMessage }
}
