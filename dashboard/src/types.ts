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

export interface PlatformContext {
  platform: string
  post_description?: string
  post_hashtags?: string[]
  account_age_days?: number
  follower_count?: number
  following_count?: number
  creator_is_minor?: boolean
}

export interface SocialMediaIn {
  platform_id: string
  post_id: string
  commenter_id: string
  creator_id: string
  comment: string
  context?: PlatformContext
}

export interface AnalysisResult {
  risk: boolean
  level: RiskLevel
  reason: string
  action: Action
}

export interface TikTokComment {
  id: string
  user: string
  text: string
  likes: number
  level: RiskLevel
  action: Action
  reason: string
  blocked: boolean
  warned: boolean
  ts: Date
}