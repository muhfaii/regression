<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useConversationStore, type Conversation } from '../stores/conversation'
import type { ChatMessage as ChatMessageType } from '../stores/conversation'
import { useApi } from '../composables/useApi'
import ChatMessageBubble from '../components/chat/ChatMessage.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const convStore = useConversationStore()
const api = useApi()

const conversations = ref<Conversation[]>([])
const sidebarLoading = ref(true)
const sending = ref(false)
const textInput = ref('')
const aiEnabled = ref(false)

async function checkAiConfig() {
  try {
    const cfg = await api.checkChatConfig()
    aiEnabled.value = cfg.configured
  } catch {
    aiEnabled.value = false
  }
}

async function fetchConversations() {
  sidebarLoading.value = true
  try {
    const res = await fetch('/api/conversations', {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
    if (res.ok) conversations.value = await res.json()
  } catch { /* ignore */ }
  finally { sidebarLoading.value = false }
}

async function loadConversation(id: string) {
  convStore.loading = true
  try {
    const res = await fetch(`/api/conversations/${id}`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    })
    if (res.ok) {
      const data = await res.json()
      convStore.setConversation(data)

      if (data.messages.length === 0) {
        await addWelcomeMessage(id)
        const r2 = await fetch(`/api/conversations/${id}`, {
          headers: { Authorization: `Bearer ${auth.token}` },
        })
        if (r2.ok) convStore.setConversation(await r2.json())
      }
    } else if (res.status === 404) {
      router.push('/dashboard')
    }
  } catch { /* ignore */ }
  finally { convStore.loading = false }
}

async function addWelcomeMessage(id: string) {
  await fetch(`/api/conversations/${id}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
    body: JSON.stringify({
      role: 'assistant',
      content_type: 'text',
      payload: {
        text: 'What would you like to do?',
        actions: ['guide', 'browse'],
      },
    }),
  })
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })
}

function switchConversation(id: string) {
  router.push(`/conversations/${id}`)
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

function goToDashboard() {
  router.push('/dashboard')
}

async function sendTextMessage() {
  const text = textInput.value.trim()
  if (!text || !convStore.currentId) return

  sending.value = true
  try {
    if (aiEnabled.value) {
      try {
        const data = await api.sendChatMessage(convStore.currentId, text)
        convStore.addMessage(data.user_message as ChatMessageType)
        convStore.addMessage(data.assistant_message as ChatMessageType)
        textInput.value = ''
        return
      } catch {
        aiEnabled.value = false
      }
    }
    // Direct send (no AI or AI unavailable)
    const res = await fetch(`/api/conversations/${convStore.currentId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({
        role: 'user',
        content_type: 'text',
        payload: { text },
      }),
    })
    if (res.ok) {
      const msg: ChatMessageType = await res.json()
      convStore.addMessage(msg)
      textInput.value = ''
    }
  } finally {
    sending.value = false
  }
}

watch(() => route.params.id, (id) => {
  if (id && typeof id === 'string') {
    loadConversation(id)
  }
})

onMounted(() => {
  checkAiConfig()
  fetchConversations()
  const id = route.params.id
  if (id && typeof id === 'string') {
    loadConversation(id)
  }
})
</script>

<template>
  <div class="conv-shell">
    <!-- Sidebar -->
    <aside class="conv-sidebar">
      <div class="sidebar-header">
        <button class="btn-new" @click="startNew">+ New analysis</button>
        <button class="btn-dash" @click="goToDashboard">Dashboard</button>
      </div>
      <div class="sidebar-list">
        <div v-if="sidebarLoading" class="sidebar-loading">Loading…</div>
        <button
          v-for="c in conversations"
          :key="c.id"
          class="sidebar-item"
          :class="{ active: c.id === convStore.currentId }"
          @click="switchConversation(c.id)"
        >
          <div class="sidebar-item-title">{{ c.title }}</div>
          <div class="sidebar-item-meta">{{ formatDate(c.updated_at) }}</div>
        </button>
      </div>
    </aside>

    <!-- Main chat area -->
    <div class="conv-main">
      <!-- Messages -->
      <div class="msg-thread" ref="threadEl">
        <div v-if="convStore.loading" class="center-msg">Loading conversation…</div>

        <template v-for="msg in convStore.messages" :key="msg.id">
          <ChatMessageBubble :message="msg">
            <template #config="{ payload }">
              <div class="embedded-note">
                Configuration: {{ JSON.stringify(payload) }}
              </div>
            </template>
            <template #result="{ payload }">
              <div class="embedded-note">
                Result: {{ JSON.stringify(payload).slice(0, 200) }}…
              </div>
            </template>
          </ChatMessageBubble>

          <!-- Action buttons after assistant text messages with actions -->
          <div
            v-if="msg.role === 'assistant' && msg.content_type === 'text' && Array.isArray(msg.payload.actions)"
            class="action-row"
          >
            <button
              v-if="(msg.payload.actions as string[]).includes('guide')"
              class="action-chip"
              @click="router.push('/guide')"
            >
              Guide me
            </button>
            <button
              v-if="(msg.payload.actions as string[]).includes('browse')"
              class="action-chip"
              @click="router.push('/browse')"
            >
              Browse tests
            </button>
            <button
              v-if="(msg.payload.actions as string[]).includes('data')"
              class="action-chip"
              @click="router.push('/data')"
            >
              Import data
            </button>
          </div>
        </template>
      </div>

      <!-- Input bar -->
      <div class="input-bar">
        <input
          v-model="textInput"
          type="text"
          class="input-field"
          :placeholder="aiEnabled ? 'Ask about your data or analysis…' : 'Type a message…'"
          :disabled="!convStore.currentId || sending"
          @keydown.enter.prevent="sendTextMessage"
        />
        <button
          class="btn-send"
          :disabled="!textInput.trim() || !convStore.currentId || sending"
          @click="sendTextMessage"
        >
          Send
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conv-shell {
  display: flex;
  flex: 1;
  height: calc(100vh - var(--topbar-h));
  overflow: hidden;
}

/* Sidebar */
.conv-sidebar {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  background: var(--color-bg);
}
.sidebar-header {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-bottom: 1px solid var(--color-border);
}
.btn-new {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 9px 14px;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.15s;
}
.btn-new:hover { background: var(--color-primary-hover); }
.btn-dash {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 7px 14px;
  font-size: 12px;
  color: var(--color-text-muted);
  transition: border-color 0.15s;
}
.btn-dash:hover { border-color: var(--color-text-muted); }

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.sidebar-loading { font-size: 13px; color: var(--color-text-muted); text-align: center; padding: 24px; }
.sidebar-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  border-radius: 8px;
  border: none;
  background: none;
  margin-bottom: 2px;
  transition: background 0.1s;
}
.sidebar-item:hover { background: var(--color-surface); }
.sidebar-item.active { background: #ede9fe; }
.sidebar-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sidebar-item-meta {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

/* Main chat */
.conv-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.msg-thread {
  flex: 1;
  overflow-y: auto;
  padding: 16px 24px;
}
.center-msg {
  text-align: center;
  color: var(--color-text-muted);
  padding: 64px 0;
  font-size: 14px;
}
.action-row {
  display: flex;
  gap: 8px;
  max-width: 800px;
  margin: 0 auto 8px;
  width: 100%;
  padding-left: 42px;
}
.action-chip {
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 20px;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text);
  transition: border-color 0.15s, background 0.15s;
}
.action-chip:hover {
  border-color: var(--color-primary);
  background: #f5f3ff;
  color: var(--color-primary);
}

.embedded-note {
  font-size: 13px;
  color: var(--color-text-muted);
  background: var(--color-surface);
  border-radius: 8px;
  padding: 12px;
  margin-top: 4px;
}

/* Input bar */
.input-bar {
  display: flex;
  gap: 8px;
  padding: 16px 24px;
  border-top: 1px solid var(--color-border);
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}
.input-field {
  flex: 1;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 14px;
  background: var(--color-bg);
  transition: border-color 0.15s;
}
.input-field:focus { outline: 2px solid var(--color-primary); outline-offset: -1px; }
.input-field:disabled { opacity: 0.5; }

.btn-send {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 10px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  transition: background 0.15s;
}
.btn-send:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
