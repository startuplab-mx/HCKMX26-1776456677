import { useState } from 'react'
import { Play, Square } from 'lucide-react'
import type { TikTokComment } from '../types'

const levelColor: Record<string, string> = {
  low:    'text-green-400 bg-green-950 border-green-900',
  medium: 'text-yellow-400 bg-yellow-950 border-yellow-900',
  high:   'text-red-400 bg-red-950 border-red-900',
}

interface Props {
  comments: TikTokComment[]
  loading: boolean
  onAnalyze: (text: string, user: string, likes: number) => void
  onRunDemo: () => void
  onStopDemo: () => void
  demoRunning: boolean
}

export function TikTokPanel({ comments, loading, onAnalyze, onRunDemo, onStopDemo, demoRunning }: Props) {
  const [input, setInput] = useState('')
  const [user, setUser] = useState('')

  const handleSend = () => {
    const t = input.trim()
    const u = user.trim() || '@anon'
    if (!t) return
    onAnalyze(t, u, 0)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-800 shrink-0">
        <span className="text-[10px] font-bold tracking-widest uppercase font-mono text-pink-400">
          Comentarios · TikTok
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          {demoRunning ? (
            <button
              onClick={onStopDemo}
              className="flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded border font-mono text-red-400 bg-red-950 border-red-800 hover:bg-red-900 transition-colors"
            >
              <Square size={8} /> STOP
            </button>
          ) : (
            <button
              onClick={onRunDemo}
              disabled={loading}
              className="flex items-center gap-1 text-[9px] font-bold px-1.5 py-0.5 rounded border font-mono text-pink-400 bg-pink-950 border-pink-900 hover:bg-pink-900/60 disabled:opacity-30 transition-colors"
            >
              <Play size={8} /> DEMO
            </button>
          )}
          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded border font-mono text-pink-400 bg-pink-950 border-pink-900">
            REAL · /analyze/social
          </span>
        </div>
      </div>

      <div className="flex flex-col gap-1.5 p-2 flex-1 overflow-y-auto">
        {comments.length === 0 && (
          <p className="text-[10px] text-gray-600 font-mono text-center mt-8">
            Simula un comentario para analizarlo
          </p>
        )}
        {comments.map(c => (
          <div
            key={c.id}
            className={`p-2 rounded-md bg-[#120a18] border-l-2 font-mono text-[11px]
              ${c.blocked ? 'border-red-900 opacity-60' : c.warned ? 'border-yellow-900' : 'border-pink-900/30'}`}
          >
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="font-bold text-pink-400">{c.user}</span>
              <span className={`text-[9px] font-bold px-1 py-px rounded border ${levelColor[c.level]}`}>
                {c.level.toUpperCase()}
                {c.blocked ? ' · BLOCKED' : c.warned ? ' · WARNED' : ''}
              </span>
            </div>
            <p className={c.blocked ? 'line-through text-gray-600' : 'text-gray-400'}>{c.text}</p>
            {c.reason && <p className="text-gray-600 text-[9px] mt-0.5">{c.reason}</p>}
            <p className="text-[9px] text-gray-700 mt-0.5">
              ♥ {c.likes.toLocaleString()} · {c.ts.toLocaleTimeString()}
            </p>
          </div>
        ))}
      </div>

      <div className="border-t border-gray-800 p-2 flex flex-col gap-1.5 shrink-0">
        <input
          type="text"
          placeholder="@usuario"
          value={user}
          onChange={e => setUser(e.target.value)}
          className="w-full bg-[#0d0d18] border border-gray-800 rounded px-2 py-1
                     text-[10px] font-mono text-gray-400 placeholder-gray-700
                     focus:outline-none focus:border-pink-900"
        />
        <div className="flex gap-1.5">
          <input
            type="text"
            placeholder="Escribe un comentario para analizar…"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            className="flex-1 bg-[#0d0d18] border border-gray-800 rounded px-2 py-1
                       text-[11px] font-mono text-gray-300 placeholder-gray-700
                       focus:outline-none focus:border-pink-900"
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="px-3 py-1 rounded text-[10px] font-bold font-mono tracking-wider
                       bg-[#1a0a18] text-pink-400 border border-pink-900
                       hover:bg-[#2a0a20] disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? '…' : 'SEND'}
          </button>
        </div>
      </div>
    </div>
  )
}