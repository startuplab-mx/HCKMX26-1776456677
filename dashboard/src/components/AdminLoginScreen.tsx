import { useState } from 'react'
import { ShieldAlert, Wifi, Hash, Lock } from 'lucide-react'

const ADMIN_PASSWORD = 'guardiannode-admin'

interface AdminConn {
  serverUrl: string
  roomId: string
}

interface Props {
  onLogin: (conn: AdminConn) => void
  onBack: () => void
}

export function AdminLoginScreen({ onLogin, onBack }: Props) {
  const [form, setForm] = useState<AdminConn & { password: string }>({
    serverUrl: `ws://${window.location.hostname}:8000`,
    roomId: 'sala-demo',
    password: '',
  })
  const [error, setError] = useState('')

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (form.password !== ADMIN_PASSWORD) {
      setError('Contraseña incorrecta')
      return
    }
    onLogin({ serverUrl: form.serverUrl, roomId: form.roomId })
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f] relative overflow-hidden">
      <div className="absolute inset-0 opacity-10"
        style={{ backgroundImage: 'linear-gradient(#ef4444 1px,transparent 1px),linear-gradient(90deg,#ef4444 1px,transparent 1px)', backgroundSize: '40px 40px' }} />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-red-500/10 rounded-full blur-3xl pointer-events-none" />

      <form onSubmit={submit} className="relative z-10 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-red-500/20 border border-red-500/40 mb-4">
            <ShieldAlert className="text-red-400" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Supervisor Admin</h1>
          <p className="text-gray-500 text-sm mt-1">Acceso a monitoreo de sala en tiempo real</p>
        </div>

        <div className="bg-gray-900/80 backdrop-blur border border-gray-800 rounded-2xl p-6 space-y-4">
          <Field icon={<Wifi size={14} />} label="Servidor (IP:Puerto)">
            <input
              value={form.serverUrl}
              onChange={set('serverUrl')}
              placeholder="ws://192.168.1.10:8000"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-red-500 transition-colors"
            />
          </Field>

          <Field icon={<Hash size={14} />} label="Código de sala a supervisar">
            <input
              value={form.roomId}
              onChange={set('roomId')}
              placeholder="sala-demo"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-red-500 transition-colors"
            />
          </Field>

          <Field icon={<Lock size={14} />} label="Contraseña de administrador">
            <input
              type="password"
              value={form.password}
              onChange={set('password')}
              placeholder="••••••••"
              required
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-red-500 transition-colors"
            />
          </Field>

          {error && <p className="text-red-400 text-xs">{error}</p>}

          <button
            type="submit"
            className="w-full mt-2 bg-red-500 hover:bg-red-400 text-white font-semibold py-2.5 rounded-lg transition-colors text-sm"
          >
            Entrar como supervisor →
          </button>

          <button
            type="button"
            onClick={onBack}
            className="w-full text-gray-500 hover:text-gray-300 text-xs transition-colors py-1"
          >
            ← Volver al login normal
          </button>
        </div>
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
