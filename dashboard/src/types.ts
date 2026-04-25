export type RiskLevel = 'low' | 'medium' | 'high'
export type Action = 'allow' | 'warn' | 'block'

export interface ChatMessage {
  id: string
  from: string
  text: string
  level: RiskLevel
  blocked: boolean
  warned: boolean
  reason: string
  ts: Date
  self: boolean
}

export interface AlertEntry {
  id: string
  room: string
  from: string
  text: string
  level: RiskLevel
  reason: string
  action: Action
  ts: Date
}

export interface Stats {
  total_messages: number
  total_alerts: number
  alert_rate: number
  by_level: Record<string, number>
  by_action: Record<string, number>
}

export interface ConnectionState {
  serverUrl: string
  roomId: string
  playerId: string
  gameId: string
}
