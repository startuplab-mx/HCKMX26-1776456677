import { useState, useCallback, useEffect, useRef } from 'react'
import { JoinScreen } from './components/JoinScreen'
import { AdminLoginScreen } from './components/AdminLoginScreen'
import { SupervisorView } from './components/SupervisorView'
import { ChatPanel } from './components/ChatPanel'
import { DashboardPanel } from './components/DashboardPanel'
import { useGameSocket } from './hooks/useGameSocket'
import { useDashboardSocket } from './hooks/useDashboardSocket'
import { useAlertNotifications } from './hooks/useAlertNotifications'
import { useTikTokComments } from './hooks/useTikTokComments'
import type { ConnectionState } from './types'
import { LogOut, Shield } from 'lucide-react'

type Screen =
  | { type: 'join' }
  | { type: 'admin-login' }
  | { type: 'game'; conn: ConnectionState }
  | { type: 'supervisor'; serverUrl: string; roomId: string }

export default function App() {
  const [screen, setScreen] = useState<Screen>({ type: 'join' })

  if (screen.type === 'join')
    return (
      <JoinScreen
        onJoin={conn => setScreen({ type: 'game', conn })}
        onAdminMode={() => setScreen({ type: 'admin-login' })}
      />
    )

  if (screen.type === 'admin-login')
    return (
      <AdminLoginScreen
        onLogin={({ serverUrl, roomId }) => setScreen({ type: 'supervisor', serverUrl, roomId })}
        onBack={() => setScreen({ type: 'join' })}
      />
    )

  if (screen.type === 'supervisor')
    return (
      <SupervisorView
        serverUrl={screen.serverUrl}
        roomId={screen.roomId}
        onLeave={() => setScreen({ type: 'join' })}
      />
    )

  return <MainView conn={(screen as { type: 'game'; conn: ConnectionState }).conn} onLeave={() => setScreen({ type: 'join' })} />
}

function MainView({ conn, onLeave }: { conn: ConnectionState; onLeave: () => void }) {
  const { alerts, stats, fetchStats, addAlert } = useDashboardSocket(conn.serverUrl, conn.roomId)
  const { requestPermission, notify } = useAlertNotifications()
  const { comments: tiktokComments, loading: tiktokLoading, analyzeComment, runTikTokDemo, stopTikTokDemo, demoRunning: tiktokDemoRunning } = useTikTokComments(
    conn.serverUrl,
    'guardiannode-dev-secret'
  )
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
          <DashboardPanel
            alerts={alerts}
            stats={stats}
            onRefreshStats={handleRefreshStats}
            messages={messages}
            tiktokComments={tiktokComments}
            tiktokLoading={tiktokLoading}
            onAnalyzeTikTok={analyzeComment}
            onRunTikTokDemo={runTikTokDemo}
            onStopTikTokDemo={stopTikTokDemo}
            tiktokDemoRunning={tiktokDemoRunning}
          />
        </div>
      </div>
    </div>
  )
}