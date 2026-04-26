import { useEffect } from 'react'
import { ShieldAlert, ShieldX, Shield, TrendingUp, AlertTriangle, CheckCircle, Activity } from 'lucide-react'
import type { AlertEntry, Stats, RiskLevel, ChatMessage, TikTokComment } from '../types'
import { ThreatChart } from './ThreatChart'
import { SceneToggle } from './SceneToggle'

interface Props {
  alerts: AlertEntry[]
  stats: Stats | null
  onRefreshStats: () => void
  messages: ChatMessage[]
  tiktokComments: TikTokComment[]
  tiktokLoading: boolean
  onAnalyzeTikTok: (text: string, user: string, likes: number) => void
  onRunTikTokDemo: () => void
  onStopTikTokDemo: () => void
  tiktokDemoRunning: boolean
}

const LEVEL_CONFIG: Record<RiskLevel, { color: string; bg: string; border: string; icon: React.ReactNode; label: string }> = {
  high:   { color: 'text-red-400',    bg: 'bg-red-950/50',    border: 'border-red-800',    icon: <ShieldX size={13} />,    label: 'CRÍTICO' },
  medium: { color: 'text-yellow-400', bg: 'bg-yellow-950/40', border: 'border-yellow-800', icon: <ShieldAlert size={13} />, label: 'ALERTA' },
  low:    { color: 'text-gray-400',   bg: 'bg-gray-900',      border: 'border-gray-700',   icon: <Shield size={13} />,     label: 'BAJO' },
}

export function DashboardPanel({ alerts, stats, onRefreshStats, messages, tiktokComments, tiktokLoading, onAnalyzeTikTok, onRunTikTokDemo, onStopTikTokDemo, tiktokDemoRunning }: Props) {
  useEffect(() => {
    onRefreshStats()
    const id = setInterval(onRefreshStats, 10000)
    return () => clearInterval(id)
  }, [onRefreshStats])

  const blocked = alerts.filter(a => a.action === 'block').length
  const warned  = alerts.filter(a => a.action === 'warn').length

  return (
    <div className="flex flex-col h-full bg-[#0d0d14] overflow-hidden">

      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-green-400" />
          <span className="text-sm font-semibold text-white">Centro de Monitoreo</span>
        </div>
        <span className="text-xs text-gray-600 font-mono">GUARDIAN NODE v1.0</span>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-2 p-3 shrink-0">
        <StatCard
          icon={<ShieldX size={16} className="text-red-400" />}
          label="Bloqueados"
          value={stats?.by_action?.block ?? blocked}
          color="text-red-400"
          glow="shadow-[0_0_15px_rgba(239,68,68,0.15)]"
        />
        <StatCard
          icon={<ShieldAlert size={16} className="text-yellow-400" />}
          label="Alertas"
          value={stats?.by_action?.warn ?? warned}
          color="text-yellow-400"
          glow="shadow-[0_0_15px_rgba(234,179,8,0.1)]"
        />
        <StatCard
          icon={<TrendingUp size={16} className="text-green-400" />}
          label="Analizados"
          value={stats?.total_messages ?? 0}
          color="text-green-400"
          glow=""
        />
      </div>

      {/* Threat chart */}
      <div className="px-3 pb-3 shrink-0">
        <ThreatChart alerts={alerts} />
      </div>

      {/* Scene toggle — game chat vs tiktok */}
      <div className="border-t border-gray-800 shrink-0">
        <div className="px-4 py-2 flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Simulador de escenas</span>
        </div>
      </div>
      <div className="h-72 shrink-0">
        <SceneToggle
          messages={messages}
          alerts={alerts}
          tiktokComments={tiktokComments}
          tiktokLoading={tiktokLoading}
          onAnalyzeTikTok={onAnalyzeTikTok}
          onRunTikTokDemo={onRunTikTokDemo}
          onStopTikTokDemo={onStopTikTokDemo}
          tiktokDemoRunning={tiktokDemoRunning}
        />
      </div>

      {/* Alert feed */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-b border-gray-800 shrink-0">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Feed en vivo</span>
        {alerts.length > 0 && (
          <span className="text-xs text-gray-600">{alerts.length} evento{alerts.length !== 1 ? 's' : ''}</span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {alerts.length === 0 && (
          <div className="flex flex-col items-center justify-center h-40 gap-2 text-gray-700">
            <CheckCircle size={24} />
            <span className="text-xs">Sin alertas — sistema limpio</span>
          </div>
        )}
        {alerts.map(alert => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </div>
    </div>
  )
}

function AlertCard({ alert }: { alert: AlertEntry }) {
  const cfg = LEVEL_CONFIG[alert.level] ?? LEVEL_CONFIG.low

  return (
    <div className={`msg-enter rounded-xl border p-3 space-y-1.5 ${cfg.bg} ${cfg.border} ${
      alert.level === 'high' ? 'pulse-alert' : ''
    }`}>
      <div className="flex items-center justify-between">
        <div className={`flex items-center gap-1.5 text-xs font-bold ${cfg.color}`}>
          {cfg.icon}
          <span>{cfg.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <ActionBadge action={alert.action} />
          <span className="text-[10px] text-gray-600 font-mono">
            {alert.ts.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5 text-xs">
        <span className="text-gray-500">de</span>
        <span className="text-white font-semibold font-mono">{alert.from}</span>
        {alert.room && (
          <>
            <span className="text-gray-600">sala</span>
            <span className="text-gray-400 font-mono">{alert.room}</span>
          </>
        )}
      </div>

      {alert.text && (
        <div className="text-xs text-gray-400 bg-black/30 rounded-lg px-2 py-1.5 font-mono truncate">
          "{alert.text.slice(0, 80)}{alert.text.length > 80 ? '…' : ''}"
        </div>
      )}

      <div className="flex items-start gap-1.5 text-xs">
        <AlertTriangle size={10} className={`${cfg.color} mt-0.5 shrink-0`} />
        <span className="text-gray-400">{alert.reason}</span>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, color, glow }: {
  icon: React.ReactNode; label: string; value: number; color: string; glow: string
}) {
  return (
    <div className={`bg-gray-900 border border-gray-800 rounded-xl p-3 ${glow}`}>
      <div className="flex items-center gap-1.5 mb-1">{icon}</div>
      <div className={`text-2xl font-bold ${color} font-mono`}>{value}</div>
      <div className="text-xs text-gray-600">{label}</div>
    </div>
  )
}

function ActionBadge({ action }: { action: string }) {
  const map: Record<string, string> = {
    block: 'bg-red-900/60 text-red-300 border-red-700',
    warn:  'bg-yellow-900/40 text-yellow-300 border-yellow-700',
    allow: 'bg-green-900/30 text-green-400 border-green-800',
  }
  return (
    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase font-mono ${map[action] ?? map.allow}`}>
      {action}
    </span>
  )
}