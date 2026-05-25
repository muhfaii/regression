import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SessionMode } from '../types/analysis'

const STORAGE_KEY = 'ra_session'
const TTL_MS = 30 * 60 * 1000

interface PersistedSession {
  sessionId: string
  expiry: number
}

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  const mode = ref<SessionMode | null>(null)

  function initSession(id: string) {
    sessionId.value = id
    const data: PersistedSession = { sessionId: id, expiry: Date.now() + TTL_MS }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }

  function restoreSession(): boolean {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return false
    try {
      const data: PersistedSession = JSON.parse(raw)
      if (Date.now() > data.expiry) {
        sessionStorage.removeItem(STORAGE_KEY)
        return false
      }
      sessionId.value = data.sessionId
      return true
    } catch {
      return false
    }
  }

  function setMode(m: SessionMode) {
    mode.value = m
  }

  function clearSession() {
    sessionId.value = null
    mode.value = null
    sessionStorage.removeItem(STORAGE_KEY)
  }

  return { sessionId, mode, initSession, restoreSession, setMode, clearSession }
})
