<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import { useDatasetStore } from '../../stores/dataset'
import { useResultsStore } from '../../stores/results'
import DatasetPill from './DatasetPill.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const dataset = useDatasetStore()
const results = useResultsStore()

const showMenu = ref(false)

const tabs = computed(() => {
  if (!auth.isAuthenticated) return [{ label: 'Sign in', path: '/login' }]
  return [
    { label: 'Dashboard', path: '/dashboard' },
    { label: 'Analysis', path: '/home' },
    ...(results.hasAnyResult ? [{ label: 'Results', path: '/results' }] : []),
  ]
})

function navigate(path: string) {
  showMenu.value = false
  if (path === '/home' && !dataset.isLoaded) {
    router.push('/data?message=no_data')
  } else {
    router.push(path)
  }
}

function isActive(path: string) {
  if (path === '/dashboard') return ['/dashboard'].includes(route.path)
  if (path === '/home') return ['/home', '/guide', '/browse', '/configure', '/data', '/conversations'].some(p => route.path.startsWith(p))
  return route.path === path
}

function toggleMenu() {
  showMenu.value = !showMenu.value
}

function handleSignOut() {
  showMenu.value = false
  auth.clearAuth()
  router.push('/login')
}

function goToDashboard() {
  showMenu.value = false
  router.push('/dashboard')
}

const initials = computed(() => {
  const name = auth.user?.display_name || auth.user?.email || ''
  return name.charAt(0).toUpperCase()
})
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <router-link to="/dashboard" class="logo">Infera</router-link>
    </div>
    <nav v-if="auth.isAuthenticated" class="topbar-nav" role="navigation" aria-label="Primary">
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
      <DatasetPill v-if="auth.isAuthenticated" :filename="dataset.filename" />
      <div v-if="auth.isAuthenticated" class="user-menu" @click="toggleMenu">
        <div class="user-avatar">{{ initials }}</div>
        <div v-if="showMenu" class="user-dropdown" @click.stop>
          <div class="dropdown-user-info">
            <div class="dropdown-name">{{ auth.user?.display_name || 'User' }}</div>
            <div class="dropdown-email">{{ auth.user?.email }}</div>
          </div>
          <button class="dropdown-item" @click="goToDashboard">Dashboard</button>
          <button class="dropdown-item dropdown-signout" @click="handleSignOut">Sign out</button>
        </div>
      </div>
      <button v-else class="btn-login" @click="navigate('/login')">Sign in</button>
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
  text-decoration: none;
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
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
}

/* User menu */
.user-menu {
  position: relative;
  cursor: pointer;
}
.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  user-select: none;
}
.user-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  min-width: 200px;
  z-index: 100;
  overflow: hidden;
}
.dropdown-user-info {
  padding: 12px 14px;
  border-bottom: 1px solid var(--color-border);
}
.dropdown-name { font-size: 13px; font-weight: 600; }
.dropdown-email { font-size: 12px; color: var(--color-text-muted); margin-top: 2px; }
.dropdown-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 14px;
  border: none;
  background: none;
  font-size: 13px;
  color: var(--color-text);
  transition: background 0.1s;
}
.dropdown-item:hover { background: var(--color-surface); }
.dropdown-signout { color: var(--color-red); border-top: 1px solid var(--color-border); margin-top: 4px; }

.btn-login {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 7px 16px;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.15s;
}
.btn-login:hover { background: var(--color-primary-hover); }

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
