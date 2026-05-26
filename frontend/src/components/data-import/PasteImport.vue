<script setup lang="ts">
import { ref } from 'vue'
import { useApi } from '../../composables/useApi'

const emit = defineEmits<{ (e: 'imported', data: unknown): void }>()

const api = useApi()
const text = ref('')
const loading = ref(false)
const error = ref<string | null>(null)

async function handleImport() {
  const trimmed = text.value.trim()
  if (!trimmed) return
  loading.value = true
  error.value = null
  try {
    const data = await api.pasteData(trimmed)
    emit('imported', data)
  } catch (e: any) {
    error.value = e.message ?? 'Import failed.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="paste-import">
    <label class="paste-label">Paste tab-separated or CSV data</label>
    <textarea
      v-model="text"
      class="paste-area"
      placeholder="Column1&#9;Column2&#9;Column3&#10;1&#9;2&#9;3&#10;4&#9;5&#9;6"
      rows="8"
      spellcheck="false"
    />
    <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
    <button
      class="btn-primary"
      :disabled="!text.trim() || loading"
      @click="handleImport"
    >
      <span v-if="loading">Parsing…</span>
      <span v-else>Import data</span>
    </button>
  </div>
</template>

<style scoped>
.paste-import {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.paste-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
}
.paste-area {
  width: 100%;
  font-family: monospace;
  font-size: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--color-bg);
  resize: vertical;
  color: var(--color-text);
  box-sizing: border-box;
}
.paste-area:focus {
  outline: 2px solid var(--color-primary);
}
.error-msg {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: var(--color-red);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
}
.btn-primary {
  align-self: flex-end;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 20px;
  font-weight: 600;
  font-size: 14px;
  transition: background 0.15s;
}
.btn-primary:hover:not(:disabled) { background: var(--color-primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
