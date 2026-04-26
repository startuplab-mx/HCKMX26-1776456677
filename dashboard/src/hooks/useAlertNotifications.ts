import { useCallback, useRef } from 'react'
import type { AlertEntry } from '../types'

function beep(frequency: number, duration: number, volume: number) {
  try {
    const ctx = new AudioContext()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = frequency
    osc.type = 'sine'
    gain.gain.setValueAtTime(volume, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration / 1000)
    osc.start(ctx.currentTime)
    osc.stop(ctx.currentTime + duration / 1000)
  } catch { /* no AudioContext */ }
}

export function useAlertNotifications() {
  const permission = useRef<NotificationPermission>('default')

  const requestPermission = useCallback(async () => {
    if ('Notification' in window) {
      permission.current = await Notification.requestPermission()
    }
  }, [])

  const notify = useCallback((alert: AlertEntry) => {
    if (alert.level === 'high') {
      beep(880, 350, 0.35)
      if (permission.current === 'granted') {
        new Notification('🚨 AEGIS — Amenaza CRÍTICA', {
          body: `${alert.from}: "${alert.text?.slice(0, 60)}" — ${alert.reason}`,
          icon: '/vite.svg',
          tag: alert.id,
        })
      }
    } else if (alert.level === 'medium') {
      beep(520, 180, 0.15)
    }
  }, [])

  return { requestPermission, notify }
}
