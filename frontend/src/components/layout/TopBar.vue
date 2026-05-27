<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDatasetStore } from '../../stores/dataset'
import { useResultsStore } from '../../stores/results'
import DatasetPill from './DatasetPill.vue'

const route = useRoute()
const router = useRouter()
const dataset = useDatasetStore()
const results = useResultsStore()

const tabs = computed(() => [
  { label: 'Data', path: '/data' },
  { label: 'Analyse', path: '/home' },
  ...(results.hasAnyResult ? [{ label: 'Results', path: '/results' }] : []),
])

function navigate(path: string) {
  if (path === '/home' && !dataset.isLoaded) {
    router.push('/data?message=no_data')
  } else {
    router.push(path)
  }
}

function isActive(path: string) {
  if (path === '/home') return ['/home', '/guide', '/browse', '/configure'].includes(route.path)
  return route.path === path
}
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <span class="logo">StatAssist</span>
    </div>
    <nav class="topbar-nav" role="navigation" aria-label="Primary">
      <button
        v-for="tab in tabs"
        :key="tab.path"
        class="nav-tab"
        :class="{ active: isActive(tab.path) }"
        :aria-current="isActive(tab.path) ? 'page' : undefined"
        @click="navigate(tab.path)"
      >
        {{ tab.label }}
      </button>
    </nav>
    <div class="topbar-right">
      <DatasetPill :filename="dataset.filename" />
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  padding: 0 24px;
  gap: 24px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
  position: sticky;
  top: 0;
  z-index: 50;
}
.logo {
  font-weight: 700;
  font-size: 16px;
  color: var(--color-primary);
  letter-spacing: -0.3px;
}
.topbar-nav {
  display: flex;
  gap: 4px;
  flex: 1;
}
.nav-tab {
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-muted);
  transition: background 0.15s, color 0.15s;
}
.nav-tab:hover {
  background: var(--color-surface);
  color: var(--color-text);
}
.nav-tab.active {
  background: var(--color-surface);
  color: var(--color-text);
}
.topbar-right {
  margin-left: auto;
}

@media (max-width: 768px) {
  .topbar {
    flex-wrap: wrap;
    height: auto;
    padding: 8px 12px;
    gap: 8px;
  }
  .topbar-nav {
    flex: 0 0 100%;
    order: 3;
    overflow-x: auto;
    scrollbar-width: none;
    -ms-overflow-style: none;
  }
  .topbar-nav::-webkit-scrollbar { display: none; }
  .topbar-right { margin-left: 0; }
}
</style>
