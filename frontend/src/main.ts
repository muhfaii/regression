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

import { useSessionStore } from './stores/session'
import { useDatasetStore } from './stores/dataset'
const session = useSessionStore()
const dataset = useDatasetStore()
session.restoreSession()
dataset.restoreDataset()
