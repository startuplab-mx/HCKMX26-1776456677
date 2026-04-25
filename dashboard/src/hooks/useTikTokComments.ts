import { useState, useCallback } from 'react'
import type { TikTokComment, SocialMediaIn, AnalysisResult } from '../types'

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

export function useTikTokComments(serverUrl: string, apiKey: string) {
  const [comments, setComments] = useState<TikTokComment[]>([])
  const [loading, setLoading] = useState(false)

  const analyzeComment = useCallback(async (
    text: string,
    user: string,
    likes: number,
    context?: SocialMediaIn['context']
  ) => {
    setLoading(true)

    const payload: SocialMediaIn = {
      platform_id: 'tiktok-dashboard',
      post_id: 'manual-test',
      commenter_id: user,
      creator_id: 'creator-unknown',
      comment: text,
      context,
    }

    try {
      const base = serverUrl.replace(/^ws/, 'http')
      const res = await fetch(`${base}/analyze/social`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': apiKey,
        },
        body: JSON.stringify(payload),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const result: AnalysisResult = await res.json()

      const entry: TikTokComment = {
        id: uuid(),
        user,
        text,
        likes,
        level: result.level,
        action: result.action,
        reason: result.reason,
        blocked: result.action === 'block',
        warned: result.action === 'warn',
        ts: new Date(),
      }

      setComments(prev => [entry, ...prev].slice(0, 100))
      return entry
    } catch {
      const entry: TikTokComment = {
        id: uuid(),
        user,
        text,
        likes,
        level: 'medium',
        action: 'warn',
        reason: 'Error de conexión con el servidor',
        blocked: false,
        warned: true,
        ts: new Date(),
      }
      setComments(prev => [entry, ...prev].slice(0, 100))
      return entry
    } finally {
      setLoading(false)
    }
  }, [serverUrl, apiKey])

  return { comments, loading, analyzeComment }
}