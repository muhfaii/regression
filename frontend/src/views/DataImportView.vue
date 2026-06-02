<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import FileDropZone from '../components/data-import/FileDropZone.vue'
import PasteImport from '../components/data-import/PasteImport.vue'
import SampleDataGrid from '../components/data-import/SampleDataGrid.vue'
import ColumnPreviewTable from '../components/data-import/ColumnPreviewTable.vue'
import { useApi } from '../composables/useApi'
import { useDatasetStore } from '../stores/dataset'
import { useSessionStore } from '../stores/session'
import type { DatasetPreview } from '../types/dataset'
import type { ColumnType } from '../types/dataset'

const route = useRoute()
const router = useRouter()
const dataset = useDatasetStore()
const session = useSessionStore()
const api = useApi()
const auth = useAuthStore()

const conversationId = computed(() => route.query.conversation_id as string | undefined)

type Tab = 'upload' | 'paste' | 'samples'
const activeTab = ref<Tab>('upload')

const loading = ref(false)
const error = ref<string | null>(null)
const preview = ref<DatasetPreview | null>(null)
const showReimportDialog = ref(false)
const pendingImport = ref<(() => Promise<void>) | null>(null)

const noDataMessage = computed(() =>
  route.query.message === 'no_data' ? 'Load a dataset to get started.' : null
)

async function applyPreview(data: DatasetPreview) {
  preview.value = data
  dataset.load(data)
  session.initSession(data.session_id)
}

async function guardImport(doImport: () => Promise<void>) {
  if (dataset.isLoaded) {
    pendingImport.value = doImport
    showReimportDialog.value = true
    return
  }
  await doImport()
}

async function handleFile(file: File) {
  await guardImport(async () => {
    loading.value = true
    error.value = null
    try {
      const data: DatasetPreview = await api.uploadFile(file, conversationId.value)
      await applyPreview(data)
    } catch (e: any) {
      error.value = e.message ?? 'Upload failed.'
    } finally {
      loading.value = false
    }
  })
}

async function handlePasted(data: unknown) {
  await guardImport(async () => {
    await applyPreview(data as DatasetPreview)
  })
}

async function handleSample(data: unknown) {
  await guardImport(async () => {
    await applyPreview(data as DatasetPreview)
  })
}

async function confirmReimport() {
  showReimportDialog.value = false
  dataset.clearDataset()
  session.clearSession()
  if (pendingImport.value) {
    await pendingImport.value()
  }
  pendingImport.value = null
}

function cancelReimport() {
  showReimportDialog.value = false
  pendingImport.value = null
}

function handleTypeChange(colName: string, type: ColumnType) {
  dataset.overrideColumnType(colName, type)
  if (preview.value) {
    const col = preview.value.columns.find(c => c.name === colName)
    if (col) col.override_type = type
  }
}

async function proceed() {
  const cid = conversationId.value
  if (cid) {
    // Add welcome message and redirect to conversation
    await fetch(`/api/conversations/${cid}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.token}` },
      body: JSON.stringify({
        role: 'assistant',
        content_type: 'text',
        payload: {
          text: `Dataset "${preview.value?.filename ?? 'data'}" has been loaded. What would you like to do?`,
          actions: ['guide', 'browse'],
        },
      }),
    }).catch(() => {})
    router.push(`/conversations/${cid}`)
  } else {
    router.push('/home')
  }
}

function reset() {
  preview.value = null
  error.value = null
}
</script>

<template>
  <div class="import-view">
    <div class="import-card">
      <h1 class="import-title">Import your data</h1>
      <p class="import-sub">Upload a file, paste text, or choose a sample dataset.</p>

      <div v-if="noDataMessage" class="info-banner" role="status" aria-live="polite">
        {{ noDataMessage }}
      </div>

      <div v-if="!preview">
        <!-- Tab bar -->
        <div class="tabs" role="tablist">
          <button
            v-for="t in (['upload', 'paste', 'samples'] as Tab[])"
            :key="t"
            class="tab"
            :class="{ active: activeTab === t }"
            role="tab"
            :aria-selected="activeTab === t"
            @click="activeTab = t"
          >
            {{ t === 'upload' ? 'Upload file' : t === 'paste' ? 'Paste data' : 'Sample data' }}
          </button>
        </div>

        <div class="tab-panel">
          <FileDropZone v-if="activeTab === 'upload'" @file="handleFile" />
          <PasteImport v-else-if="activeTab === 'paste'" :conversation-id="conversationId" @imported="handlePasted" />
          <SampleDataGrid v-else :conversation-id="conversationId" @imported="handleSample" />
        </div>

        <div v-if="loading" class="status-msg">Parsing file…</div>
        <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
      </div>

      <div v-else class="preview-section">
        <div class="preview-meta">
          <strong>{{ preview.filename }}</strong>
          <span class="meta-detail">{{ preview.row_count.toLocaleString() }} rows · {{ preview.columns.length }} columns</span>
        </div>

        <div v-if="preview.warnings.length" class="warnings">
          <p v-for="w in preview.warnings" :key="w" class="warning-item">⚠ {{ w }}</p>
        </div>

        <ColumnPreviewTable :columns="preview.columns" @type-change="handleTypeChange" />

        <div class="preview-actions">
          <button class="btn-ghost" @click="reset">Import different data</button>
          <button class="btn-primary" @click="proceed">Continue to analysis →</button>
        </div>
      </div>
    </div>

    <!-- Re-import confirmation dialog -->
    <dialog :open="showReimportDialog" class="confirm-dialog">
      <p>This will replace your current data. Continue?</p>
      <div class="dialog-actions">
        <button class="btn-ghost" @click="cancelReimport">Cancel</button>
        <button class="btn-danger" @click="confirmReimport">Yes, replace data</button>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.import-view {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 48px 24px;
  min-height: calc(100vh - var(--topbar-h));
}
.import-card {
  width: 100%;
  max-width: 640px;
}
.import-title { font-size: 24px; margin-bottom: 6px; }
.import-sub { color: var(--color-text-muted); margin-bottom: 24px; }
.info-banner {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 20px;
}
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 20px;
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
.status-msg { text-align: center; color: var(--color-text-muted); margin-top: 16px; }
.error-msg {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: var(--color-red);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  margin-top: 16px;
}
.preview-section { display: flex; flex-direction: column; gap: 16px; }
.preview-meta { display: flex; align-items: baseline; gap: 12px; font-size: 14px; }
.meta-detail { color: var(--color-text-muted); font-size: 13px; }
.warnings { display: flex; flex-direction: column; gap: 4px; }
.warning-item {
  font-size: 12px;
  color: var(--color-amber);
  background: var(--color-amber-bg);
  padding: 6px 10px;
  border-radius: 6px;
}
.preview-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
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
.btn-ghost {
  background: none;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 9px 16px;
  font-size: 14px;
  color: var(--color-text-muted);
  transition: border-color 0.15s;
}
.btn-ghost:hover { border-color: var(--color-text-muted); color: var(--color-text); }
.btn-danger {
  background: var(--color-red);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 9px 16px;
  font-weight: 600;
}
.confirm-dialog {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 24px;
  max-width: 360px;
  box-shadow: 0 8px 30px rgba(0,0,0,0.12);
}
.dialog-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }
</style>
