import { useState, useCallback, useEffect, useRef } from 'react'
import { JoinScreen } from './components/JoinScreen'
import { ChatPanel } from './components/ChatPanel'
import { DashboardPanel } from './components/DashboardPanel'
import { useGameSocket } from './hooks/useGameSocket'
import { useDashboardSocket } from './hooks/useDashboardSocket'
import { useAlertNotifications } from './hooks/useAlertNotifications'
import type { ConnectionState } from './types'
import { LogOut, Shield } from 'lucide-react'

export default function App() {
  const [conn, setConn] = useState<ConnectionState | null>(null)
  if (!conn) return <JoinScreen onJoin={setConn} />
  return <MainView conn={conn} onLeave={() => setConn(null)} />
}

function MainView({ conn, onLeave }: { conn: ConnectionState; onLeave: () => void }) {
  const { alerts, stats, fetchStats, addAlert } = useDashboardSocket(conn.serverUrl, conn.roomId)
  const { requestPermission, notify } = useAlertNotifications()
  const prevCount = useRef(0)

  useEffect(() => { requestPermission() }, [requestPermission])

  useEffect(() => {
    if (alerts.length > prevCount.current) notify(alerts[0])
    prevCount.current = alerts.length
  }, [alerts, notify])

  const handleAlert = useCallback((alert: object) => {
    addAlert(alert as Parameters<typeof addAlert>[0])
  }, [addAlert])

  const { messages, status, players, connect, disconnect, sendMessage } = useGameSocket({
    serverUrl: conn.serverUrl,
    roomId: conn.roomId,
    playerId: conn.playerId,
    gameId: conn.gameId,
    onAlert: handleAlert,
  })

  useState(() => { connect() })

  const handleLeave = () => { disconnect(); onLeave() }
  const handleRefreshStats = useCallback(() => fetchStats('guardiannode-dev-secret'), [fetchStats])

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0f]">
      <div className="flex items-center justify-between px-4 py-2 bg-[#080810] border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-2">
          <Shield size={16} className="text-green-400" />
          <span className="text-sm font-bold text-white tracking-tight">GuardianNode</span>
          <span className="text-xs text-gray-600 font-mono">·</span>
          <span className="text-xs text-gray-500 font-mono">{conn.roomId}</span>
          <span className="text-xs text-gray-600 font-mono">·</span>
          <span className="text-xs text-green-400 font-mono">{conn.playerId}</span>
        </div>
        <button
          onClick={handleLeave}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-800"
        >
          <LogOut size={12} /> Salir
        </button>
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-[3] min-w-0">
          <ChatPanel messages={messages} status={status} players={players} onSend={sendMessage} />
        </div>
        <div className="flex-[2] min-w-0 border-l border-gray-800">
          <DashboardPanel alerts={alerts} stats={stats} onRefreshStats={handleRefreshStats} />
        </div>
      </div>
    </div>
  )
}
