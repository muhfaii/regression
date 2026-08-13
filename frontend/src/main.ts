import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.mount('#app')

import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
const auth = useAuthStore()
auth.restore()
useThemeStore().restore()
