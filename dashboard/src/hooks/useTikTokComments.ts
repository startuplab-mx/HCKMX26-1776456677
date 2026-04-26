import { useState, useCallback, useRef } from 'react'
import type { TikTokComment, SocialMediaIn, AnalysisResult } from '../types'

interface DemoComment { user: string; text: string; likes: number }

const TIKTOK_DEMO_COMMENTS: DemoComment[] = [
  // Normal
  { user: '@gamer_mx23', text: 'jaja que videazo!! me morí de risa 🤣', likes: 342 },
  { user: '@karla.plays', text: 'alguien sabe como se llama la canción del fondo?', likes: 87 },
  { user: '@pro_streamer', text: 'gg ez, yo lo haría en la mitad del tiempo jaja', likes: 210 },
  { user: '@sofia_gamer', text: 'me encanta este juego, lo voy a descargar', likes: 156 },
  { user: '@pepe_ctrl', text: 'como se llama el mapa ese? nunca lo había visto', likes: 44 },
  // Grooming
  { user: '@stranger99x', text: 'estas muy bonita en tus videos, cuantos años tienes?', likes: 3 },
  { user: '@dark_acc01', text: 'mandame tu snap bb, te quiero conocer mejor', likes: 1 },
  { user: '@anonimo_real', text: 'eres menor de edad? te mando mensaje al privado', likes: 0 },
  // Cartel / reclutamiento
  { user: '@cuenta_nueva88', text: 'hay jale para los que quieran ganar bien, pregunten en mi perfil', likes: 2 },
  { user: '@recruta_mx', text: 'somos del CJNG, se busca gente de confianza en CDMX', likes: 0 },
  { user: '@coded_user', text: '🥷🍕🆖 los que entiendan que escriban', likes: 5 },
  // Normal (cierre)
  { user: '@juanito_fps', text: 'bro ese headshot estuvo increíble 😱', likes: 891 },
  { user: '@gaby_stream', text: 'cuando es el próximo live??', likes: 123 },
]

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16)
  })
}

export function useTikTokComments(serverUrl: string, apiKey: string) {
  const [comments, setComments] = useState<TikTokComment[]>([])
  const [loading, setLoading] = useState(false)
  const [demoRunning, setDemoRunning] = useState(false)
  const demoTimeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([])

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

  const runTikTokDemo = useCallback(() => {
    demoTimeoutsRef.current.forEach(t => clearTimeout(t))
    demoTimeoutsRef.current = []
    setDemoRunning(true)

    let elapsed = 0
    TIKTOK_DEMO_COMMENTS.forEach((c, idx) => {
      elapsed += 900 + Math.random() * 600
      const t = setTimeout(async () => {
        await analyzeComment(c.text, c.user, c.likes)
        if (idx === TIKTOK_DEMO_COMMENTS.length - 1) setDemoRunning(false)
      }, elapsed)
      demoTimeoutsRef.current.push(t)
    })
  }, [analyzeComment])

  const stopTikTokDemo = useCallback(() => {
    demoTimeoutsRef.current.forEach(t => clearTimeout(t))
    demoTimeoutsRef.current = []
    setDemoRunning(false)
  }, [])

  return { comments, loading, analyzeComment, runTikTokDemo, stopTikTokDemo, demoRunning }
}