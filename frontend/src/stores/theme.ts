import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'ra_theme'

export type Theme = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>('dark')

  function apply() {
    document.documentElement.classList.toggle('theme-light', theme.value === 'light')
  }

  function restore() {
    const saved = localStorage.getItem(STORAGE_KEY)
    theme.value = saved === 'light' ? 'light' : 'dark'
    apply()
  }

  function toggle() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem(STORAGE_KEY, theme.value)
    apply()
  }

  return { theme, restore, toggle }
})
