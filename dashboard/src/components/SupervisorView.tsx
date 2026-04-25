import { ShieldAlert, Users, LogOut, Wifi, WifiOff, AlertTriangle, Shield, Ban } from 'lucide-react'
import { useSupervisorSocket } from '../hooks/useSupervisorSocket'
import type { RiskLevel } from '../types'

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

export function SupervisorView({ serverUrl, roomId, onLeave }: Props) {
  const { messages, alerts, players, connected } = useSupervisorSocket(serverUrl, roomId)

  const blocked = messages.filter(m => m.blocked).length
  const warned = messages.filter(m => m.warned).length
  const total = messages.length

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
        <button
          onClick={onLeave}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors px-2 py-1 rounded hover:bg-gray-800"
        >
          <LogOut size={12} /> Salir
        </button>
      </div>

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
              <p className="text-gray-600 text-xs text-center py-8">Esperando mensajes...</p>
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

        {/* Right: players + alerts */}
        <div className="flex-[1] flex flex-col min-w-0 min-w-[220px]">
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
