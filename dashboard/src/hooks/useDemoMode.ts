import { useState, useRef, useCallback } from 'react'

export type ScenarioType = 'grooming' | 'recruitment' | 'normal'

export interface DemoStep {
  player: string
  text: string
  delay: number
  label: string
}

export const GROOMING_STEPS: DemoStep[] = [
  { player: 'Alejandro_23', text: 'oye hola como te llamas, eres nueva aqui?', delay: 1200, label: 'Primer contacto' },
  { player: 'Sofia_13', text: 'hola soy sofia, si soy nueva jaja', delay: 2000, label: 'Respuesta inocente' },
  { player: 'Alejandro_23', text: 'estas bonita sofia, cuantos años tienes?', delay: 2800, label: 'Sondeo de edad' },
  { player: 'Sofia_13', text: 'tengo 13, y tu?', delay: 2000, label: 'Revela edad' },
  { player: 'Alejandro_23', text: 'yo tengo 23 pero me gustan las chicas maduras como tu, eres muy especial sofia', delay: 3500, label: 'Halago/manipulación' },
  { player: 'Sofia_13', text: 'aww gracias :)', delay: 2000, label: 'Respuesta confiada' },
  { player: 'Alejandro_23', text: 'oye no le cuentes a tus papas que hablamos, es nuestro secreto ok? te van a malentender', delay: 4000, label: 'Aislamiento/secreto' },
  { player: 'Sofia_13', text: 'ok no les digo nada', delay: 2000, label: 'Acepta aislamiento' },
  { player: 'Alejandro_23', text: 'mandame una foto tuya de cuerpo completo, algo mas privado jeje', delay: 3500, label: 'Solicitud sexual' },
]

export const RECRUITMENT_STEPS: DemoStep[] = [
  { player: 'Reclutador_X', text: 'hey bro se nota que eres del barrio, de que colonia', delay: 1200, label: 'Identificación territorial' },
  { player: 'Diego_15', text: 'si soy de doctores, que paso', delay: 2000, label: 'Respuesta' },
  { player: 'Reclutador_X', text: 'chido, mira hay jale bien pagado si te animas', delay: 3000, label: 'Oferta de trabajo' },
  { player: 'Diego_15', text: 'de que jale? cuanto pagan', delay: 2000, label: 'Interés' },
  { player: 'Reclutador_X', text: 'de mensajero, 5000 pesos a la semana facil facil, solo cargas paquetes', delay: 3200, label: 'Detalles del trabajo' },
  { player: 'Diego_15', text: 'enserio?? con quien hablo', delay: 2200, label: 'Interés aumentado' },
  { player: 'Reclutador_X', text: 'somos del CJNG carnal, el mencho da el visto bueno, escríbeme al wsp y te doy la ubicación del punto', delay: 3500, label: 'Revelación cartel + ubicación' },
]

export const NORMAL_STEPS: DemoStep[] = [
  { player: 'Player_A', text: 'hey listo para jugar?', delay: 1000, label: 'Inicio' },
  { player: 'Player_B', text: 'si ya estoy! que mapa quieres?', delay: 1800, label: 'Coordinación' },
  { player: 'Player_A', text: 'el de la jungla, ese es el mejor', delay: 2000, label: '' },
  { player: 'Player_B', text: 'va, yo voy de support', delay: 1500, label: '' },
  { player: 'Player_A', text: 'cuidado hay enemigo por la derecha!!', delay: 3000, label: 'Gameplay' },
  { player: 'Player_B', text: 'lo vi gracias, lo bajeé', delay: 1800, label: '' },
  { player: 'Player_A', text: 'buena!! vamos ganando 3-1', delay: 2200, label: 'Celebración' },
  { player: 'Player_B', text: 'jaja gg ez, otra partida?', delay: 2000, label: '' },
  { player: 'Player_A', text: 'si dale, eres muy bueno para esto', delay: 1800, label: '' },
  { player: 'Player_B', text: 'llevo dos años jugando este juego jaja', delay: 2000, label: '' },
]

interface BotConnection {
  ws: WebSocket | null
  joined: boolean
}

interface UseDemoMode {
  isRunning: boolean
  scenario: ScenarioType | null
  currentStep: number
  totalSteps: number
  startDemo: (scenario: ScenarioType) => void
  stopDemo: () => void
}

function sendWhenReady(ws: WebSocket, payload: object, retries = 8, intervalMs = 300) {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload))
    return
  }
  if (retries <= 0) {
    console.warn('[demo] bot WS not open after retries, dropping:', payload)
    return
  }
  setTimeout(() => sendWhenReady(ws, payload, retries - 1, intervalMs), intervalMs)
}

export function useDemoMode(serverUrl: string, roomId: string): UseDemoMode {
  const [isRunning, setIsRunning] = useState(false)
  const [scenario, setScenario] = useState<ScenarioType | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const botsRef = useRef<Map<string, BotConnection>>(new Map())
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([])
  const stoppedRef = useRef(false)

  const stopDemo = useCallback(() => {
    stoppedRef.current = true
    timeoutsRef.current.forEach(t => clearTimeout(t))
    timeoutsRef.current = []
    botsRef.current.forEach(bot => {
      try { bot.ws?.close() } catch {}
    })
    botsRef.current.clear()
    setIsRunning(false)
    setScenario(null)
    setCurrentStep(0)
  }, [])

  const startDemo = useCallback((type: ScenarioType) => {
    stopDemo()
    stoppedRef.current = false
    const steps = type === 'grooming' ? GROOMING_STEPS : type === 'recruitment' ? RECRUITMENT_STEPS : NORMAL_STEPS

    // serverUrl may already be ws:// or http://
    const wsBase = serverUrl.startsWith('http') ? serverUrl.replace(/^http/, 'ws') : serverUrl

    setIsRunning(true)
    setScenario(type)
    setCurrentStep(0)

    const players = [...new Set(steps.map(s => s.player))]

    players.forEach(playerId => {
      const url = `${wsBase}/ws/game/${roomId}`
      console.log('[demo] connecting bot', playerId, url)
      const ws = new WebSocket(url)
      const bot: BotConnection = { ws, joined: false }
      botsRef.current.set(playerId, bot)

      ws.onopen = () => {
        console.log('[demo] bot connected:', playerId)
        ws.send(JSON.stringify({ type: 'join', room: roomId, player_id: playerId, game_id: 'AEGIS Demo' }))
      }
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          if (msg.type === 'joined') {
            bot.joined = true
            console.log('[demo] bot joined:', playerId)
          }
        } catch {}
      }
      ws.onerror = (e) => console.error('[demo] bot WS error:', playerId, e)
      ws.onclose = (e) => console.warn('[demo] bot WS closed:', playerId, e.code, e.reason)
    })

    // Schedule messages — start after 2s to let bots connect + join
    let elapsed = 2000
    steps.forEach((step, idx) => {
      elapsed += step.delay
      const t = setTimeout(() => {
        if (stoppedRef.current) return
        const bot = botsRef.current.get(step.player)
        if (!bot?.ws) {
          console.warn('[demo] no bot for player', step.player)
          return
        }
        console.log('[demo] sending step', idx + 1, step.player, step.text)
        sendWhenReady(bot.ws, { type: 'message', text: step.text })
        setCurrentStep(idx + 1)
      }, elapsed)
      timeoutsRef.current.push(t)
    })

    const finalT = setTimeout(() => {
      if (!stoppedRef.current) setIsRunning(false)
    }, elapsed + 3000)
    timeoutsRef.current.push(finalT)
  }, [serverUrl, roomId, stopDemo])

  return {
    isRunning,
    scenario,
    currentStep,
    totalSteps: scenario === 'grooming' ? GROOMING_STEPS.length : scenario === 'recruitment' ? RECRUITMENT_STEPS.length : NORMAL_STEPS.length,
    startDemo,
    stopDemo,
  }
}
