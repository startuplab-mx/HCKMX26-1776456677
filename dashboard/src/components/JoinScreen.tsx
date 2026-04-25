import { useState } from 'react'
import { Shield, Wifi, User, Hash, Gamepad2 } from 'lucide-react'
import type { ConnectionState } from '../types'

interface Props {
  onJoin: (state: ConnectionState) => void
}

export function JoinScreen({ onJoin }: Props) {
  const [form, setForm] = useState<ConnectionState>({
    serverUrl: 'ws://localhost:8000',
    roomId: 'sala-demo',
    playerId: '',
    gameId: 'GuardianNode Demo',
  })

  const set = (k: keyof ConnectionState) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.playerId.trim()) return
    onJoin(form)
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f] relative overflow-hidden">
      {/* Background grid */}
      <div className="absolute inset-0 opacity-10"
        style={{ backgroundImage: 'linear-gradient(#22c55e 1px,transparent 1px),linear-gradient(90deg,#22c55e 1px,transparent 1px)', backgroundSize: '40px 40px' }} />

      {/* Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-green-500/10 rounded-full blur-3xl pointer-events-none" />

      <form onSubmit={submit} className="relative z-10 w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-green-500/20 border border-green-500/40 mb-4">
            <Shield className="text-green-400" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">GuardianNode</h1>
          <p className="text-gray-500 text-sm mt-1">Simulador de protección infantil</p>
        </div>

        <div className="bg-gray-900/80 backdrop-blur border border-gray-800 rounded-2xl p-6 space-y-4">

          <Field icon={<Wifi size={14} />} label="Servidor (IP:Puerto)">
            <input
              value={form.serverUrl}
              onChange={set('serverUrl')}
              placeholder="ws://192.168.1.10:8000"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500 transition-colors"
            />
          </Field>

          <Field icon={<Hash size={14} />} label="Código de sala">
            <input
              value={form.roomId}
              onChange={set('roomId')}
              placeholder="sala-demo"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500 transition-colors"
            />
          </Field>

          <Field icon={<User size={14} />} label="Tu nombre de jugador">
            <input
              value={form.playerId}
              onChange={set('playerId')}
              placeholder="Jugador1"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500 transition-colors"
            />
          </Field>

          <Field icon={<Gamepad2 size={14} />} label="Nombre del juego">
            <input
              value={form.gameId}
              onChange={set('gameId')}
              placeholder="MiJuego"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-green-500 transition-colors"
            />
          </Field>

          <button
            type="submit"
            className="w-full mt-2 bg-green-500 hover:bg-green-400 text-black font-semibold py-2.5 rounded-lg transition-colors text-sm"
          >
            Entrar al simulador →
          </button>
        </div>

        <p className="text-center text-gray-600 text-xs mt-4">
          Dos jugadores deben usar el mismo servidor + código de sala
        </p>
      </form>
    </div>
  )
}

function Field({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="flex items-center gap-1.5 text-xs text-gray-400 mb-1.5">
        <span className="text-gray-500">{icon}</span>
        {label}
      </label>
      {children}
    </div>
  )
}
