import { useMemo } from 'react'
import type { AlertEntry } from '../types'

const BUCKETS = 24       // 24 × 5s = 2 min window
const BUCKET_MS = 5_000

interface Props {
  alerts: AlertEntry[]
}

export function ThreatChart({ alerts }: Props) {
  const buckets = useMemo(() => {
    const now = Date.now()
    return Array.from({ length: BUCKETS }, (_, i) => {
      const start = now - (BUCKETS - i) * BUCKET_MS
      const end = start + BUCKET_MS
      const inBucket = alerts.filter(a => {
        const t = a.ts.getTime()
        return t >= start && t < end
      })
      return {
        count: inBucket.length,
        high: inBucket.filter(a => a.level === 'high').length,
        medium: inBucket.filter(a => a.level === 'medium').length,
      }
    })
  }, [alerts])

  const max = Math.max(1, ...buckets.map(b => b.count))
  const W = 280
  const H = 44
  const bw = W / BUCKETS
  const totalHigh = alerts.filter(a => a.level === 'high').length
  const totalMed  = alerts.filter(a => a.level === 'medium').length

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-3">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs text-gray-500">Amenazas · últimos 2 min</span>
        <div className="flex gap-2 text-[10px] font-mono">
          {totalHigh > 0 && <span className="text-red-400">{totalHigh} crítico{totalHigh !== 1 ? 's' : ''}</span>}
          {totalMed  > 0 && <span className="text-yellow-400">{totalMed} alerta{totalMed !== 1 ? 's' : ''}</span>}
          {totalHigh === 0 && totalMed === 0 && <span className="text-green-400">sin amenazas</span>}
        </div>
      </div>

      <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {/* baseline */}
        <line x1={0} y1={H} x2={W} y2={H} stroke="#1f2937" strokeWidth={1} />

        {buckets.map((b, i) => {
          const barH = b.count === 0 ? 1 : Math.max(4, (b.count / max) * H)
          const x = i * bw + 0.5
          const y = H - barH
          const fill = b.high > 0 ? '#ef4444' : b.medium > 0 ? '#eab308' : '#1f2937'
          const opacity = b.count === 0 ? 0.3 : 0.85
          return (
            <rect key={i} x={x} y={y} width={bw - 1} height={barH} rx={1.5}
              fill={fill} opacity={opacity} />
          )
        })}

        {/* pulse dot on last bucket if recent alert */}
        {buckets[BUCKETS - 1].count > 0 && (
          <circle cx={W - bw / 2} cy={H - Math.max(4, (buckets[BUCKETS - 1].count / max) * H) - 3}
            r={3} fill={buckets[BUCKETS - 1].high > 0 ? '#ef4444' : '#eab308'} opacity={0.9} />
        )}
      </svg>

      <div className="flex justify-between text-[9px] text-gray-700 mt-1 font-mono">
        <span>−2 min</span>
        <span>ahora</span>
      </div>
    </div>
  )
}
