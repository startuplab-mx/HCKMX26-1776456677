import { useState } from 'react'
import type { ChatMessage, AlertEntry, TikTokComment } from '../types'
import { TikTokPanel } from './TikTokPanel'

type Scene = 'game' | 'tiktok'

interface Props {
  messages: ChatMessage[]
  alerts: AlertEntry[]
  tiktokComments: TikTokComment[]
  tiktokLoading: boolean
  onAnalyzeTikTok: (text: string, user: string, likes: number) => void
  onRunTikTokDemo: () => void
  onStopTikTokDemo: () => void
  tiktokDemoRunning: boolean
}

const levelColor: Record<string, string> = {
  low:    'text-green-400 bg-green-950 border-green-900',
  medium: 'text-yellow-400 bg-yellow-950 border-yellow-900',
  high:   'text-red-400 bg-red-950 border-red-900',
}

export function SceneToggle({ messages, alerts, tiktokComments, tiktokLoading, onAnalyzeTikTok, onRunTikTokDemo, onStopTikTokDemo, tiktokDemoRunning }: Props) {
  const [scene, setScene] = useState<Scene>('game')

  return (
    <div className="flex flex-col h-full">
      <div className="flex m-2 bg-[#0d0d18] border border-gray-800 rounded-lg p-0.5 gap-0.5 shrink-0">
        {(['game', 'tiktok'] as Scene[]).map(s => (
          <button
            key={s}
            onClick={() => setScene(s)}
            className={`flex-1 py-1.5 rounded-md text-[10px] font-bold tracking-widest uppercase
                        transition-all flex items-center justify-center gap-1.5 font-mono
              ${scene === s
                ? s === 'game'
                  ? 'bg-[#131327] text-green-400 border border-green-900/50'
                  : 'bg-[#131327] text-pink-400 border border-pink-900/50'
                : 'text-gray-600 hover:text-gray-500'}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full
              ${scene === s ? (s === 'game' ? 'bg-green-400' : 'bg-pink-400') : 'bg-gray-700'}`}
            />
            {s === 'game' ? 'Multijugador' : 'TikTok'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-hidden bg-[#080810] border border-gray-800/60 rounded-lg mx-2 mb-2">
        {scene === 'game' ? (
          <div className="flex flex-col h-full">
            <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-800 shrink-0">
              <span className="text-[10px] font-bold tracking-widest uppercase font-mono text-green-400">
                Chat de sala
              </span>
              <span className="ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded border font-mono text-green-400 bg-green-950 border-green-900">
                LIVE · {alerts.length} alertas
              </span>
            </div>
            <div className="flex flex-col gap-1.5 p-2 flex-1 overflow-y-auto">
              {messages.length === 0 && (
                <p className="text-[10px] text-gray-600 font-mono text-center mt-8">
                  Sin mensajes aún
                </p>
              )}
              {messages.slice(-20).map(m => (
                <div key={m.id}
                  className={`p-2 rounded-md bg-[#0a0a18] border-l-2 font-mono text-[11px]
                    ${m.blocked ? 'border-red-900 opacity-60' : m.warned ? 'border-yellow-900' : 'border-green-900/40'}`}
                >
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <span className={`font-bold ${m.self ? 'text-blue-400' : m.from === 'SISTEMA' ? 'text-gray-500' : 'text-green-400'}`}>
                      {m.from}
                    </span>
                    <span className={`text-[9px] font-bold px-1 py-px rounded border ${levelColor[m.level]}`}>
                      {m.level.toUpperCase()}
                      {m.blocked ? ' · BLOCKED' : m.warned ? ' · WARNED' : ''}
                    </span>
                  </div>
                  <p className="text-gray-400">{m.text}</p>
                  {m.reason && <p className="text-gray-600 text-[9px] mt-0.5">{m.reason}</p>}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <TikTokPanel
            comments={tiktokComments}
            loading={tiktokLoading}
            onAnalyze={onAnalyzeTikTok}
            onRunDemo={onRunTikTokDemo}
            onStopDemo={onStopTikTokDemo}
            demoRunning={tiktokDemoRunning}
          />
        )}
      </div>
    </div>
  )
}