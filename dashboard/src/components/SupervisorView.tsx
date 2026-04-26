import { ShieldAlert, Users, LogOut, Wifi, WifiOff, AlertTriangle, Shield, Ban, Play, Square, BarChart2 } from 'lucide-react'
import { useSupervisorSocket } from '../hooks/useSupervisorSocket'
import { useDemoMode } from '../hooks/useDemoMode'
import { PatternTimeline } from './PatternTimeline'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { RiskLevel } from '../types'
import { useMemo } from 'react'

interface Props {
  serverUrl: string
  roomId: string
  onLeave: () => void
}

const LEVEL_COLOR: Record<RiskLevel, string> = {
  low: 'text-green-400 bg-green-500/10 border-green-500/30',
  medium: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  high: 'text-red-400 bg-red-500/10 border-red-500/30',
}

const LEVEL_DOT: Record<RiskLevel, string> = {
  low: 'bg-green-400',
  medium: 'bg-yellow-400',
  high: 'bg-red-400',
}

const CHART_COLORS: Record<RiskLevel, string> = {
  low: '#22c55e',
  medium: '#eab308',
  high: '#ef4444',
}

export function SupervisorView({ serverUrl, roomId, onLeave }: Props) {
  const { messages, alerts, players, connected } = useSupervisorSocket(serverUrl, roomId)
  const { isRunning, scenario, currentStep, totalSteps, startDemo, stopDemo } = useDemoMode(serverUrl, roomId)

  const blocked = messages.filter(m => m.blocked).length
  const warned = messages.filter(m => m.warned).length
  const total = messages.length

  const riskChartData = useMemo(() => {
    const counts = { low: 0, medium: 0, high: 0 }
    messages.forEach(m => { counts[m.level]++ })
    return [
      { name: 'Bajo', value: counts.low, level: 'low' as RiskLevel },
      { name: 'Medio', value: counts.medium, level: 'medium' as RiskLevel },
      { name: 'Alto', value: counts.high, level: 'high' as RiskLevel },
    ]
  }, [messages])

  const timelineData = useMemo(() => {
    const buckets: Record<string, { low: number; medium: number; high: number }> = {}
    messages.forEach(m => {
      const key = m.ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      if (!buckets[key]) buckets[key] = { low: 0, medium: 0, high: 0 }
      buckets[key][m.level]++
    })
    return Object.entries(buckets).slice(-12).map(([time, v]) => ({ time, ...v }))
  }, [messages])

  return (
    <div className="h-screen flex flex-col bg-[#0a0a0f]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#080810] border-b border-red-900/40 shrink-0">
        <div className="flex items-center gap-3">
          <ShieldAlert size={16} className="text-red-400" />
          <span className="text-sm font-bold text-white tracking-tight">Supervisor</span>
          <span className="text-xs text-gray-600 font-mono">·</span>
          <span className="text-xs text-red-400 font-mono">{roomId}</span>
          <span className="text-xs text-gray-600 font-mono">·</span>
          {connected
            ? <span className="flex items-center gap-1 text-xs text-green-400"><Wifi size={10} /> EN VIVO</span>
            : <span className="flex items-center gap-1 text-xs text-gray-500"><WifiOff size={10} /> Reconectando...</span>
          }
        </div>
        <div className="flex items-center gap-2">
          {/* Demo controls */}
          {isRunning ? (
            <button
              onClick={stopDemo}
              className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border border-red-800/60 hover:bg-red-950/30 transition-colors"
            >
              <Square size={10} /> Detener demo
            </button>
          ) : (
            <>
              <button
                onClick={() => startDemo('normal')}
                className="flex items-center gap-1.5 text-xs text-green-400 hover:text-green-300 px-2 py-1 rounded border border-green-800/60 hover:bg-green-950/30 transition-colors"
              >
                <Play size={10} /> Demo Normal
              </button>
              <button
                onClick={() => startDemo('grooming')}
                className="flex items-center gap-1.5 text-xs text-purple-400 hover:text-purple-300 px-2 py-1 rounded border border-purple-800/60 hover:bg-purple-950/30 transition-colors"
              >
                <Play size={10} /> Demo Grooming
              </button>
              <button
                onClick={() => startDemo('recruitment')}
                className="flex items-center gap-1.5 text-xs text-orange-400 hover:text-orange-300 px-2 py-1 rounded border border-orange-800/60 hover:bg-orange-950/30 transition-colors"
              >
                <Play size={10} /> Demo Reclutamiento
              </button>
            </>
          )}
          <button
            onClick={onLeave}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-800"
          >
            <LogOut size={12} /> Salir
          </button>
        </div>
      </div>

      {/* Demo progress bar */}
      {isRunning && (
        <div className="bg-gray-900/80 border-b border-gray-800 px-4 py-1.5 shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-gray-400 font-mono shrink-0">
              {scenario === 'grooming' ? 'GROOMING' : 'RECLUTAMIENTO'} · paso {currentStep}/{totalSteps}
            </span>
            <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${scenario === 'grooming' ? 'bg-purple-500' : scenario === 'recruitment' ? 'bg-orange-500' : 'bg-green-500'}`}
                style={{ width: `${(currentStep / totalSteps) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* Left: message feed */}
        <div className="flex-[3] flex flex-col min-w-0 border-r border-gray-800">
          {/* Stats bar */}
          <div className="flex gap-4 px-4 py-2 border-b border-gray-800 bg-gray-900/40 shrink-0">
            <Stat label="Mensajes" value={total} color="text-white" />
            <Stat label="Alertas" value={warned} color="text-yellow-400" />
            <Stat label="Bloqueados" value={blocked} color="text-red-400" />
          </div>

          {/* Feed */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1 flex flex-col-reverse">
            {messages.length === 0 && (
              <p className="text-gray-600 text-xs text-center py-8">
                {isRunning ? 'Iniciando demo...' : 'Esperando mensajes...'}
              </p>
            )}
            {messages.map(msg => (
              <div key={msg.id} className={`rounded-lg px-3 py-2 border text-xs ${msg.blocked ? 'border-red-800/50 bg-red-950/20' : msg.warned ? 'border-yellow-800/40 bg-yellow-950/10' : 'border-gray-800/60 bg-gray-900/30'}`}>
                <div className="flex items-center justify-between mb-0.5">
                  <div className="flex items-center gap-1.5">
                    {msg.blocked && <Ban size={10} className="text-red-400" />}
                    {msg.warned && !msg.blocked && <AlertTriangle size={10} className="text-yellow-400" />}
                    {!msg.blocked && !msg.warned && <Shield size={10} className="text-green-500/50" />}
                    <span className="font-mono text-gray-300 font-semibold">{msg.from}</span>
                    <span className={`px-1.5 py-0.5 rounded border text-[10px] font-mono ${LEVEL_COLOR[msg.level]}`}>
                      {msg.level}
                    </span>
                    {msg.blocked && <span className="text-red-400 text-[10px] font-semibold">BLOQUEADO</span>}
                  </div>
                  <span className="text-gray-600 font-mono text-[10px]">
                    {msg.ts.toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-gray-200 leading-relaxed">{msg.text}</p>
                {msg.reason && (
                  <p className="text-gray-500 mt-0.5 italic">{msg.reason}</p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: players + charts + alerts + timeline */}
        <div className="flex-[1] flex flex-col min-w-0 min-w-[260px] overflow-y-auto">
          {/* Players */}
          <div className="border-b border-gray-800 p-3 shrink-0">
            <div className="flex items-center gap-1.5 mb-2">
              <Users size={12} className="text-gray-500" />
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Jugadores ({players.length})</span>
            </div>
            {players.length === 0
              ? <p className="text-gray-600 text-xs">Ninguno conectado</p>
              : players.map(p => (
                  <div key={p} className="flex items-center gap-2 py-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
                    <span className="text-xs text-gray-300 font-mono truncate">{p}</span>
                  </div>
                ))
            }
          </div>

          {/* Risk distribution chart */}
          {total > 0 && (
            <div className="border-b border-gray-800 p-3 shrink-0">
              <div className="flex items-center gap-1.5 mb-2">
                <BarChart2 size={12} className="text-gray-500" />
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Distribución de riesgo</span>
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <BarChart data={riskChartData} margin={{ top: 0, right: 4, bottom: 0, left: -20 }}>
                  <XAxis dataKey="name" tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 6, fontSize: 10 }}
                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  />
                  <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                    {riskChartData.map((entry) => (
                      <Cell key={entry.level} fill={CHART_COLORS[entry.level]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Timeline chart */}
          {timelineData.length > 1 && (
            <div className="border-b border-gray-800 p-3 shrink-0">
              <div className="flex items-center gap-1.5 mb-2">
                <BarChart2 size={12} className="text-gray-500" />
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Actividad por tiempo</span>
              </div>
              <ResponsiveContainer width="100%" height={80}>
                <BarChart data={timelineData} margin={{ top: 0, right: 4, bottom: 0, left: -20 }}>
                  <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 9, fill: '#6b7280' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#111827', border: '1px solid #374151', borderRadius: 6, fontSize: 10 }}
                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                  />
                  <Bar dataKey="high" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="medium" stackId="a" fill="#eab308" />
                  <Bar dataKey="low" stackId="a" fill="#22c55e" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Pattern timeline during demo */}
          {isRunning && scenario && scenario !== 'normal' && (
            <div className="border-b border-gray-800 p-3 shrink-0">
              <PatternTimeline scenario={scenario as 'grooming' | 'recruitment'} currentStep={currentStep} />
            </div>
          )}

          {/* Alerts */}
          <div className="flex-1 flex flex-col overflow-hidden p-3">
            <div className="flex items-center gap-1.5 mb-2 shrink-0">
              <AlertTriangle size={12} className="text-red-400" />
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Alertas ({alerts.length})</span>
            </div>
            <div className="flex-1 overflow-y-auto space-y-1.5">
              {alerts.length === 0 && <p className="text-gray-600 text-xs">Sin alertas</p>}
              {alerts.map(a => (
                <div key={a.id} className={`rounded-lg p-2 border text-xs ${LEVEL_COLOR[a.level]}`}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="font-mono font-semibold">{a.from}</span>
                    <span className="flex items-center gap-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${LEVEL_DOT[a.level]}`} />
                      {a.level}
                    </span>
                  </div>
                  <p className="text-gray-200 truncate">{a.text}</p>
                  <p className="text-gray-400 mt-0.5 italic text-[10px]">{a.reason}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`text-sm font-bold font-mono ${color}`}>{value}</span>
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  )
}
