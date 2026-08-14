<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useDatasetStore } from '../stores/dataset'
import { useSessionStore } from '../stores/session'
import ColumnPreviewTable from '../components/data-import/ColumnPreviewTable.vue'
import MissingDataPanel from '../components/data-prep/MissingDataPanel.vue'
import RecodeComputePanel from '../components/data-prep/RecodeComputePanel.vue'
import ReverseScorePanel from '../components/data-prep/ReverseScorePanel.vue'
import MergeDatasetPanel from '../components/data-prep/MergeDatasetPanel.vue'
import type { DatasetPreview, ColumnType } from '../types/dataset'

const route = useRoute()
const router = useRouter()
const dataset = useDatasetStore()
const session = useSessionStore()
const auth = useAuthStore()

const conversationId = computed(() => route.query.conversation_id as string | undefined)

type Tab = 'missing' | 'recode' | 'reverse' | 'merge'
const activeTab = ref<Tab>('missing')

function handleUpdated(preview: DatasetPreview) {
  dataset.load(preview)
}

function handleTypeChange(colName: string, type: ColumnType) {
  dataset.overrideColumnType(colName, type)
}

async function proceed() {
  const cid = conversationId.value
  if (cid) {
    await fetch(`/api/conversations/${cid}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({
        role: 'assistant',
        content_type: 'text',
        payload: {
          text: `Dataset "${dataset.filename ?? 'data'}" has been prepared. What would you like to do?`,
          actions: ['guide', 'browse'],
        },
      }),
    }).catch(() => {})
    router.push(`/conversations/${cid}`)
  } else {
    router.push('/home')
  }
}
</script>

<template>
  <div class="prep-view">
    <div class="prep-card">
      <h1 class="prep-title">Prepare your data</h1>
      <p class="prep-sub">Clean missing values, recode or compute variables, reverse-score scale items, or merge in another dataset — all optional.</p>

      <div v-if="session.sessionId" class="prep-body">
        <ColumnPreviewTable :columns="dataset.columns" @type-change="handleTypeChange" />

        <div class="tabs" role="tablist">
          <button class="tab" :class="{ active: activeTab === 'missing' }" @click="activeTab = 'missing'">Missing data</button>
          <button class="tab" :class="{ active: activeTab === 'recode' }" @click="activeTab = 'recode'">Recode / Compute</button>
          <button class="tab" :class="{ active: activeTab === 'reverse' }" @click="activeTab = 'reverse'">Reverse-score</button>
          <button class="tab" :class="{ active: activeTab === 'merge' }" @click="activeTab = 'merge'">Merge dataset</button>
        </div>

        <div class="tab-panel">
          <MissingDataPanel v-if="activeTab === 'missing'" :session-id="session.sessionId" :columns="dataset.columns" @updated="handleUpdated" />
          <RecodeComputePanel v-else-if="activeTab === 'recode'" :session-id="session.sessionId" :columns="dataset.columns" @updated="handleUpdated" />
          <ReverseScorePanel v-else-if="activeTab === 'reverse'" :session-id="session.sessionId" :columns="dataset.columns" @updated="handleUpdated" />
          <MergeDatasetPanel v-else :session-id="session.sessionId" :columns="dataset.columns" @updated="handleUpdated" />
        </div>

        <div class="prep-actions">
          <span class="meta-detail">{{ dataset.rowCount.toLocaleString() }} rows · {{ dataset.columns.length }} columns</span>
          <button class="btn-primary" @click="proceed">Continue to analysis →</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prep-view {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 48px 24px;
  min-height: calc(100vh - var(--topbar-h));
}
.prep-card { width: 100%; max-width: 720px; }
.prep-title { font-size: 24px; margin-bottom: 6px; }
.prep-sub { color: var(--color-text-muted); margin-bottom: 24px; }
.prep-body { display: flex; flex-direction: column; gap: 20px; }
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border);
}
.tab {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  cursor: pointer;
  margin-bottom: -1px;
  transition: color 0.15s, border-color 0.15s;
}
.tab:hover { color: var(--color-text); }
.tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}
.tab-panel { min-height: 160px; }
.prep-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.meta-detail { color: var(--color-text-muted); font-size: 13px; }
.btn-primary {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
  font-weight: 600;
  font-size: 14px;
  transition: background 0.15s;
}
.btn-primary:hover { background: var(--color-primary-hover); }
</style>
