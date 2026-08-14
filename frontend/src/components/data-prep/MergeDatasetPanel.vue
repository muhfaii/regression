<script setup lang="ts">
import { ref } from 'vue'
import { useApi } from '../../composables/useApi'
import type { ColumnInfo, DatasetPreview } from '../../types/dataset'

const props = defineProps<{ sessionId: string; columns: ColumnInfo[] }>()
const emit = defineEmits<{ (e: 'updated', preview: DatasetPreview): void }>()

const api = useApi()

const file = ref<File | null>(null)
const leftOn = ref('')
const rightOn = ref('')
const how = ref<'inner' | 'left' | 'right' | 'outer'>('left')
const loading = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)

function handleFile(e: Event) {
  const input = e.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

async function apply() {
  if (!file.value || !leftOn.value || !rightOn.value) return
  loading.value = true
  error.value = null
  message.value = null
  try {
    const preview = await api.mergeDatasets(props.sessionId, file.value, leftOn.value, rightOn.value, how.value)
    message.value = preview.warnings[0] ?? 'Applied.'
    emit('updated', preview)
    file.value = null
    rightOn.value = ''
  } catch (e: any) {
    error.value = e.message ?? 'Could not merge datasets.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="panel">
    <p class="panel-sub">Join another CSV or Excel file onto your current dataset using a shared key column.</p>

    <div class="field-group">
      <label class="field-label">Second dataset</label>
      <input type="file" accept=".csv,.xlsx" class="file-input" @change="handleFile" />
    </div>

    <div class="field-group">
      <label class="field-label">Key column in current dataset</label>
      <select v-model="leftOn" class="select">
        <option value="" disabled>Select a column…</option>
        <option v-for="c in columns" :key="c.name" :value="c.name">{{ c.name }}</option>
      </select>
    </div>

    <div class="field-group">
      <label class="field-label">Key column in second dataset</label>
      <input v-model="rightOn" class="text-input" placeholder="e.g. id" />
    </div>

    <div class="field-group">
      <label class="field-label">Join type</label>
      <select v-model="how" class="select">
        <option value="left">Left join (keep all current rows)</option>
        <option value="inner">Inner join (keep only matching rows)</option>
        <option value="right">Right join (keep all rows from second dataset)</option>
        <option value="outer">Outer join (keep all rows from both)</option>
      </select>
    </div>

    <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
    <div v-if="message" class="success-msg">{{ message }}</div>

    <button class="btn-primary" :disabled="!file || !leftOn || !rightOn || loading" @click="apply">
      <span v-if="loading">Merging…</span>
      <span v-else>Merge</span>
    </button>
  </div>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 16px; }
.panel-sub { color: var(--color-text-muted); font-size: 13px; margin: 0; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 600; color: var(--color-text-muted); }
.select, .text-input, .file-input {
  border: 1px solid var(--color-border); border-radius: 8px; padding: 8px 10px;
  font-size: 13px; background: var(--color-bg); color: var(--color-text);
}
.error-msg {
  background: #fef2f2; border: 1px solid #fecaca; color: var(--color-red);
  border-radius: 8px; padding: 10px 14px; font-size: 13px;
}
.success-msg {
  background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d;
  border-radius: 8px; padding: 10px 14px; font-size: 13px;
}
.btn-primary {
  align-self: flex-start; background: var(--color-primary); color: #fff; border: none;
  border-radius: 8px; padding: 10px 20px; font-weight: 600; font-size: 14px; transition: background 0.15s;
}
.btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
