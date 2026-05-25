<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FileDropZone from '../components/data-import/FileDropZone.vue'
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

const loading = ref(false)
const error = ref<string | null>(null)
const preview = ref<DatasetPreview | null>(null)
const showReimportDialog = ref(false)
const pendingFile = ref<File | null>(null)

const noDataMessage = computed(() =>
  route.query.message === 'no_data' ? 'Load a dataset to get started.' : null
)

async function handleFile(file: File) {
  if (dataset.isLoaded) {
    pendingFile.value = file
    showReimportDialog.value = true
    return
  }
  await doImport(file)
}

async function confirmReimport() {
  showReimportDialog.value = false
  dataset.clearDataset()
  session.clearSession()
  if (pendingFile.value) await doImport(pendingFile.value)
  pendingFile.value = null
}

function cancelReimport() {
  showReimportDialog.value = false
  pendingFile.value = null
}

async function doImport(file: File) {
  loading.value = true
  error.value = null
  try {
    const data: DatasetPreview = await api.uploadFile(file)
    preview.value = data
    dataset.load(data)
    session.initSession(data.session_id)
  } catch (e: any) {
    error.value = e.message ?? 'Upload failed.'
  } finally {
    loading.value = false
  }
}

function handleTypeChange(colName: string, type: ColumnType) {
  dataset.overrideColumnType(colName, type)
  if (preview.value) {
    const col = preview.value.columns.find(c => c.name === colName)
    if (col) col.override_type = type
  }
}

function proceed() {
  router.push('/home')
}
</script>

<template>
  <div class="import-view">
    <div class="import-card">
      <h1 class="import-title">Import your data</h1>
      <p class="import-sub">Upload a file to begin your analysis session.</p>

      <div v-if="noDataMessage" class="info-banner" role="alert">
        {{ noDataMessage }}
      </div>

      <div v-if="!preview">
        <FileDropZone @file="handleFile" />

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
          <button class="btn-ghost" @click="preview = null; error = null">Upload a different file</button>
          <button class="btn-primary" @click="proceed">Continue to analysis →</button>
        </div>
      </div>
    </div>

    <!-- Re-import confirmation dialog -->
    <dialog :open="showReimportDialog" class="confirm-dialog">
      <p>This will clear the current session. Continue?</p>
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
.import-title {
  font-size: 24px;
  margin-bottom: 6px;
}
.import-sub {
  color: var(--color-text-muted);
  margin-bottom: 24px;
}
.info-banner {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  margin-bottom: 20px;
}
.status-msg {
  text-align: center;
  color: var(--color-text-muted);
  margin-top: 16px;
}
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
.preview-meta {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-size: 14px;
}
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
