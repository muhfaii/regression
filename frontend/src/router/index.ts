import { createRouter, createWebHistory } from 'vue-router'
import { useDatasetStore } from '../stores/dataset'
import { useAnalysisStore } from '../stores/analysis'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/data' },
    { path: '/data', component: () => import('../views/DataImportView.vue') },
    { path: '/home', component: () => import('../views/HomeModeView.vue') },
    { path: '/guide', component: () => import('../views/GuideMeView.vue') },
    { path: '/browse', component: () => import('../views/BrowseTestsView.vue') },
    { path: '/configure', component: () => import('../views/AnalysisConfigView.vue') },
    { path: '/results', component: () => import('../views/ResultsView.vue') },
    { path: '/share/:token', component: () => import('../views/ShareView.vue') },
  ],
})

// Guard: screens beyond /data require a loaded dataset (except parameter_input tests)
const GUARDED = ['/home', '/guide', '/browse', '/configure', '/results']

router.beforeEach((to) => {
  if (GUARDED.includes(to.path)) {
    const dataset = useDatasetStore()
    const analysis = useAnalysisStore()
    if (to.path === '/configure' || to.path === '/browse') {
      if (analysis.selectedTest?.type === 'parameter_input') {
        return
      }
    }
    if (!dataset.isLoaded) {
      return { path: '/data', query: { message: 'no_data' } }
    }
  }
})

export default router
