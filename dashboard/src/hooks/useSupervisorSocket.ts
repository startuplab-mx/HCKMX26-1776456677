import { useState, useCallback, useRef, useEffect } from 'react'
import type { RiskLevel, Action } from '../types'

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

export interface SupervisorMessage {
  id: string
  from: string
  text: string
  level: RiskLevel
  blocked: boolean
  warned: boolean
  risk: boolean
  reason: string
  ts: Date
}

export interface SupervisorAlert {
  id: string
  from: string
  text: string
  level: RiskLevel
  reason: string
  action: Action
  ts: Date
}

interface UseSupervisorSocket {
  messages: SupervisorMessage[]
  alerts: SupervisorAlert[]
  players: string[]
  connected: boolean
}

export function useSupervisorSocket(serverUrl: string, roomId: string): UseSupervisorSocket {
  const [messages, setMessages] = useState<SupervisorMessage[]>([])
  const [alerts, setAlerts] = useState<SupervisorAlert[]>([])
  const [players, setPlayers] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    const url = `${serverUrl}/ws/game/${roomId}/supervisor`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setTimeout(connect, 3000)
    }

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)

        if (msg.type === 'room_state') {
          setPlayers(msg.players ?? [])
        } else if (msg.type === 'player_joined') {
          setPlayers(msg.players ?? [])
        } else if (msg.type === 'player_left') {
          setPlayers(msg.players ?? [])
        } else if (msg.type === 'supervisor_message') {
          setMessages(prev => [{
            id: uuid(),
            from: msg.from,
            text: msg.text,
            level: msg.level,
            blocked: msg.blocked,
            warned: msg.warned,
            risk: msg.risk,
            reason: msg.reason,
            ts: new Date(msg.ts),
          }, ...prev].slice(0, 200))
        } else if (msg.type === 'supervisor_alert') {
          setAlerts(prev => [{
            id: uuid(),
            from: msg.from,
            text: msg.text,
            level: msg.level,
            reason: msg.reason,
            action: msg.action,
            ts: new Date(msg.ts),
          }, ...prev].slice(0, 100))
        }
      } catch {}
    }
  }, [serverUrl, roomId])

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [connect])

  return { messages, alerts, players, connected }
}
