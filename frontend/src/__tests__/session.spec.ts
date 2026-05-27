import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSessionStore } from '../stores/session'

const STORAGE_KEY = 'ra_session'

beforeEach(() => {
  setActivePinia(createPinia())
  sessionStorage.clear()
  vi.restoreAllMocks()
})

describe('useSessionStore', () => {
  it('initSession stores sessionId and writes to sessionStorage', () => {
    const store = useSessionStore()
    store.initSession('abc-123')

    expect(store.sessionId).toBe('abc-123')
    const raw = sessionStorage.getItem(STORAGE_KEY)
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw!)
    expect(parsed.sessionId).toBe('abc-123')
    expect(parsed.expiry).toBeGreaterThan(Date.now())
  })

  it('restoreSession returns true and restores sessionId when not expired', () => {
    const store = useSessionStore()
    store.initSession('abc-123')

    // Simulate a page refresh: new pinia instance but sessionStorage still has the entry
    setActivePinia(createPinia())
    const freshStore = useSessionStore()
    expect(freshStore.sessionId).toBeNull() // not yet restored

    const restored = freshStore.restoreSession()
    expect(restored).toBe(true)
    expect(freshStore.sessionId).toBe('abc-123')
  })

  it('restoreSession returns false and clears storage when expired', () => {
    const store = useSessionStore()
    store.initSession('abc-123')

    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 31 * 60 * 1000)

    setActivePinia(createPinia())
    const freshStore = useSessionStore()
    const restored = freshStore.restoreSession()

    expect(restored).toBe(false)
    expect(freshStore.sessionId).toBeNull()
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('clearSession removes sessionStorage entry', () => {
    const store = useSessionStore()
    store.initSession('abc-123')
    expect(sessionStorage.getItem(STORAGE_KEY)).not.toBeNull()

    store.clearSession()
    expect(store.sessionId).toBeNull()
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
