<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

interface Conversation {
  id: string
  title: string
  dataset_name: string | null
  created_at: string
  updated_at: string
  message_count: number
}

const router = useRouter()
const auth = useAuthStore()

const conversations = ref<Conversation[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    const res = await fetch('/api/conversations', {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
    if (res.ok) {
      conversations.value = await res.json()
    }
  } catch {
    // silently fail
  } finally {
    loading.value = false
  }
})

function formatDate(iso: string): string {
  const d = new Date(iso)
  const day = String(d.getDate()).padStart(2, '0')
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const year = String(d.getFullYear()).slice(-2)
  return `${day}-${month}-${year}`
}

async function startNew() {
  try {
    const res = await fetch('/api/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({}),
    })
    if (res.ok) {
      const conv = await res.json()
      router.push(`/data?conversation_id=${conv.id}`)
      return
    }
  } catch { /* fall through */ }
  router.push('/data')
}

function openConversation(id: string) {
  router.push(`/conversations/${id}`)
}
</script>

<template>
  <div class="dashboard">
    <div class="dash-header">
      <div>
        <h1 class="dash-title">Welcome{{ auth.user?.display_name ? ', ' + auth.user.display_name : '' }}</h1>
        <p class="dash-sub">Start a new analysis or pick up where you left off.</p>
      </div>
      <button class="btn-primary" @click="startNew">+ New analysis</button>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <div class="spinner" />
      <p>Loading conversations…</p>
    </div>

    <!-- Empty state -->
    <div v-else-if="conversations.length === 0" class="empty-state">
      <div class="empty-icon">⬡</div>
      <h2 class="empty-title">No analyses yet</h2>
      <p class="empty-desc">Import a dataset and run your first statistical analysis.</p>
      <button class="btn-primary" @click="startNew">Start your first analysis</button>
    </div>

    <!-- Conversation list -->
    <div v-else class="conv-list">
      <div class="conv-list-header">Recent analyses</div>
      <button
        v-for="conv in conversations"
        :key="conv.id"
        class="conv-card"
        @click="openConversation(conv.id)"
      >
        <div class="conv-info">
          <div class="conv-title">{{ conv.title }}</div>
          <div class="conv-meta">
            <span v-if="conv.dataset_name" class="conv-dataset">{{ conv.dataset_name }}</span>
            <span class="conv-date">{{ formatDate(conv.updated_at) }}</span>
            <span class="conv-msgs">{{ conv.message_count }} message{{ conv.message_count === 1 ? '' : 's' }}</span>
          </div>
        </div>
        <span class="conv-arrow">→</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 720px;
  margin: 0 auto;
  padding: 48px 24px;
}
.dash-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 40px;
  gap: 24px;
}
.dash-title { font-size: 24px; }
.dash-sub { color: var(--color-text-muted); margin-top: 4px; font-size: 14px; }
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  transition: background 0.15s;
}
.btn-primary:hover { background: var(--color-primary-hover); }

/* Loading */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 64px 0;
  color: var(--color-text-muted);
}
.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 64px 24px;
  border: 1px dashed var(--color-border);
  border-radius: 16px;
  gap: 12px;
}
.empty-icon { font-size: 40px; color: var(--color-border); }
.empty-title { font-size: 18px; }
.empty-desc { font-size: 14px; color: var(--color-text-muted); max-width: 300px; line-height: 1.5; }

/* Conversation list */
.conv-list { display: flex; flex-direction: column; }
.conv-list-header {
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
  margin-bottom: 12px;
}
.conv-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-bg);
  margin-bottom: 8px;
  transition: border-color 0.15s, box-shadow 0.15s;
  gap: 12px;
}
.conv-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(79,70,229,0.08);
}
.conv-info { flex: 1; min-width: 0; }
.conv-title { font-size: 14px; font-weight: 600; color: var(--color-text); margin-bottom: 4px; }
.conv-meta { display: flex; gap: 12px; font-size: 12px; color: var(--color-text-muted); flex-wrap: wrap; }
.conv-dataset { font-weight: 500; color: var(--color-primary); }
.conv-arrow { font-size: 16px; color: var(--color-text-muted); flex-shrink: 0; }
</style>
