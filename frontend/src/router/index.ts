import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useDatasetStore } from '../stores/dataset'
import { useAnalysisStore } from '../stores/analysis'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/register', component: () => import('../views/RegisterView.vue') },
    { path: '/dashboard', component: () => import('../views/DashboardView.vue'), meta: { requiresAuth: true } },
    { path: '/data', component: () => import('../views/DataImportView.vue'), meta: { requiresAuth: true } },
    { path: '/home', component: () => import('../views/HomeModeView.vue'), meta: { requiresAuth: true } },
    { path: '/guide', component: () => import('../views/GuideMeView.vue'), meta: { requiresAuth: true } },
    { path: '/browse', component: () => import('../views/BrowseTestsView.vue'), meta: { requiresAuth: true } },
    { path: '/configure', component: () => import('../views/AnalysisConfigView.vue'), meta: { requiresAuth: true } },
    { path: '/results', component: () => import('../views/ResultsView.vue'), meta: { requiresAuth: true } },
    { path: '/conversations/:id', component: () => import('../views/ConversationView.vue'), meta: { requiresAuth: true } },
    { path: '/share/:token', component: () => import('../views/ShareView.vue') },
  ],
})

// Auth guard: redirect unauthenticated users to /login
router.beforeEach((to) => {
  if (to.meta?.requiresAuth) {
    const auth = useAuthStore()
    if (!auth.isAuthenticated) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }
})

// Dataset guard: analysis screens require a loaded dataset
const DATASET_GUARDED = ['/home', '/guide', '/browse', '/configure', '/results']

router.afterEach((to) => {
  if (DATASET_GUARDED.includes(to.path)) {
    const dataset = useDatasetStore()
    const analysis = useAnalysisStore()
    if (to.path === '/configure' || to.path === '/browse') {
      if (analysis.selectedTest?.type === 'parameter_input') {
        return
      }
    }
    if (!dataset.isLoaded) {
      router.replace({ path: '/data', query: { message: 'no_data' } })
    }
  }
})

export default router
