import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const STORAGE_KEY = 'ra_auth'

interface AuthUser {
  id: string
  email: string
  display_name: string
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(null)
  const user = ref<AuthUser | null>(null)

  const isAuthenticated = computed(() => token.value !== null)

  function save() {
    if (token.value && user.value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: token.value, user: user.value }))
    } else {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  function restore(): boolean {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return false
    try {
      const data = JSON.parse(raw)
      token.value = data.token ?? null
      user.value = data.user ?? null
      return isAuthenticated.value
    } catch {
      localStorage.removeItem(STORAGE_KEY)
      return false
    }
  }

  function setAuth(t: string, u: AuthUser) {
    token.value = t
    user.value = u
    save()
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem(STORAGE_KEY)
  }

  return { token, user, isAuthenticated, restore, setAuth, clearAuth }
})
