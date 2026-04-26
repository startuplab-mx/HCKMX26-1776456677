import { useEffect, useState, useCallback } from 'react'
import type { AlertEntry, Stats } from '../types'

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

export function useDashboardSocket(serverUrl: string, roomId: string) {
  const [alerts, setAlerts] = useState<AlertEntry[]>([])
  const [stats, setStats] = useState<Stats | null>(null)

  const addAlert = useCallback((raw: Partial<AlertEntry> & { level: AlertEntry['level']; reason: string; action: AlertEntry['action'] }) => {
    const entry: AlertEntry = {
      id: uuid(),
      room: raw.room ?? roomId,
      from: raw.from ?? '?',
      text: raw.text ?? '',
      level: raw.level,
      reason: raw.reason,
      action: raw.action,
      ts: new Date(),
    }
    setAlerts(prev => [entry, ...prev].slice(0, 100))
  }, [roomId])

  // Load initial stats snapshot
  const fetchStats = useCallback(async (apiKey: string) => {
    try {
      const base = serverUrl.replace(/^ws/, 'http')
      const res = await fetch(`${base}/stats`, { headers: { 'X-API-Key': apiKey, 'ngrok-skip-browser-warning': '1' } })
      if (res.ok) setStats(await res.json())
    } catch { /* ignore */ }
  }, [serverUrl])

  useEffect(() => {
    if (!serverUrl || !roomId) return

    // Load initial stats on mount
    fetchStats('guardiannode-dev-secret')

    let socket: WebSocket | null = null
    let dead = false
    let pingId: ReturnType<typeof setInterval>

    const connect = () => {
      if (dead) return
      socket = new WebSocket(`${serverUrl}/ws/game/${roomId}/dashboard`)

      socket.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'alert') addAlert(msg)
        // Real-time stats pushed by server after each moderation
        if (msg.type === 'stats_update') {
          const { type: _, ...statsData } = msg
          setStats(statsData)
        }
      }

      socket.onclose = () => {
        if (!dead) setTimeout(connect, 3000)
      }

      socket.onerror = () => socket?.close()

      pingId = setInterval(() => {
        if (socket?.readyState === WebSocket.OPEN) socket.send('ping')
      }, 20000)
    }

    const tid = setTimeout(connect, 100)

    return () => {
      dead = true
      clearTimeout(tid)
      clearInterval(pingId)
      socket?.close()
    }
  }, [serverUrl, roomId, addAlert, fetchStats])

  return { alerts, stats, fetchStats, addAlert }
}
