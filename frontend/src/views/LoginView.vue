<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref<string | null>(null)
const loading = ref(false)

async function handleLogin() {
  error.value = null
  loading.value = true
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value, password: password.value }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Login failed')
    }
    const data = await res.json()
    auth.setAuth(data.access_token, data.user)
    router.push('/dashboard')
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-view">
    <div class="auth-card">
      <h1 class="auth-title">Sign in to Infera</h1>
      <p class="auth-sub">Welcome back. Sign in to continue your analysis.</p>

      <form class="auth-form" @submit.prevent="handleLogin">
        <label class="field">
          <span class="field-label">Email</span>
          <input
            v-model="email"
            type="email"
            class="field-input"
            placeholder="you@example.com"
            required
            autocomplete="email"
          />
        </label>

        <label class="field">
          <span class="field-label">Password</span>
          <input
            v-model="password"
            type="password"
            class="field-input"
            placeholder="Enter your password"
            required
            autocomplete="current-password"
          />
        </label>

        <div v-if="error" class="error-msg" role="alert">{{ error }}</div>

        <button type="submit" class="btn-primary" :disabled="loading" :aria-busy="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </button>
      </form>

      <p class="auth-alt">
        Don't have an account?
        <router-link to="/register" class="auth-link">Create one</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-view {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - var(--topbar-h));
  padding: 48px 24px;
}
.auth-card {
  width: 100%;
  max-width: 400px;
}
.auth-title { font-size: 22px; margin-bottom: 6px; }
.auth-sub { color: var(--color-text-muted); margin-bottom: 28px; }
.auth-form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 4px; }
.field-label { font-size: 13px; font-weight: 600; color: var(--color-text); }
.field-input {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
  background: var(--color-bg);
  transition: border-color 0.15s;
}
.field-input:focus { outline: 2px solid var(--color-primary); outline-offset: -1px; }
.error-msg {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: var(--color-red);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
}
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 11px 20px;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.15s;
  width: 100%;
}
.btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.auth-alt { text-align: center; font-size: 13px; color: var(--color-text-muted); margin-top: 24px; }
.auth-link { color: var(--color-primary); font-weight: 600; text-decoration: none; }
.auth-link:hover { text-decoration: underline; }
</style>
