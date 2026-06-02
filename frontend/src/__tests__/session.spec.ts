import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore } from '../stores/session'

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('useSessionStore', () => {
  it('initSession stores sessionId', () => {
    const store = useSessionStore()
    store.initSession('abc-123')

    expect(store.sessionId).toBe('abc-123')
  })

  it('clearSession resets state', () => {
    const store = useSessionStore()
    store.initSession('abc-123')
    expect(store.sessionId).toBe('abc-123')

    store.clearSession()
    expect(store.sessionId).toBeNull()
  })
})
