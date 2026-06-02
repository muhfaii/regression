import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SessionMode } from '../types/analysis'

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  const mode = ref<SessionMode | null>(null)

  function initSession(id: string) {
    sessionId.value = id
  }

  function setMode(m: SessionMode) {
    mode.value = m
  }

  function clearSession() {
    sessionId.value = null
    mode.value = null
  }

  return { sessionId, mode, initSession, setMode, clearSession }
})
