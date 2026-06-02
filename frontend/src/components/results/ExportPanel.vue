<script setup lang="ts">
import { ref } from 'vue'
import { useResultsStore } from '../../stores/results'
import { useSessionStore } from '../../stores/session'
import { useApi } from '../../composables/useApi'

const results = useResultsStore()
const session = useSessionStore()
const api = useApi()

const copyDone = ref(false)
const downloading = ref(false)
const sharing = ref(false)
const shareUrl = ref<string | null>(null)
const shareUrlCopied = ref(false)
const error = ref<string | null>(null)

async function copyApa() {
  const apa = results.activeResult?.interpretation?.apa
  if (!apa) return
  await navigator.clipboard.writeText(apa)
  copyDone.value = true
  setTimeout(() => { copyDone.value = false }, 1500)
}

async function downloadWord() {
  const result = results.activeResult
  const sid = session.sessionId
  if (!result || !sid) return
  downloading.value = true
  error.value = null
  try {
    const blob = await api.exportWord(result.result_id, sid)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${result.test_key}_results.docx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    error.value = e.message ?? 'Download failed.'
  } finally {
    downloading.value = false
  }
}

async function createShare() {
  const result = results.activeResult
  const sid = session.sessionId
  if (!result || !sid) return
  sharing.value = true
  error.value = null
  try {
    const { url } = await api.createShareLink(result.result_id, sid)
    shareUrl.value = window.location.origin + url
  } catch (e: any) {
    error.value = e.message ?? 'Share failed.'
  } finally {
    sharing.value = false
  }
}

async function copyShareUrl() {
  if (!shareUrl.value) return
  await navigator.clipboard.writeText(shareUrl.value)
  shareUrlCopied.value = true
  setTimeout(() => { shareUrlCopied.value = false }, 1500)
}
</script>

<template>
  <div class="export-panel">
    <h3 class="panel-title">Export</h3>

    <div class="export-actions">
      <button class="export-btn" @click="copyApa" :disabled="!results.activeResult">
        {{ copyDone ? '✓ Copied' : 'Copy APA 7th edition' }}
      </button>

      <button class="export-btn" @click="downloadWord" :disabled="downloading || !results.activeResult">
        {{ downloading ? 'Building…' : 'Download Word' }}
      </button>

      <button
        v-if="!shareUrl"
        class="export-btn"
        @click="createShare"
        :disabled="sharing || !results.activeResult"
      >
        {{ sharing ? 'Generating…' : 'Share link' }}
      </button>
    </div>

    <!-- Share URL row — shown after link is created -->
    <div v-if="shareUrl" class="share-row">
      <input class="share-input" :value="shareUrl" readonly />
      <button class="export-btn share-copy-btn" @click="copyShareUrl">
        {{ shareUrlCopied ? '✓' : 'Copy' }}
      </button>
    </div>

    <p v-if="error" class="export-error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.export-panel {
  border-top: 1px solid var(--color-border);
  padding-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}
.export-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.export-btn {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 7px;
  padding: 7px 14px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.export-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}
.export-btn:disabled {
  opacity: 0.45;
  cursor: default;
}
.share-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.share-input {
  flex: 1;
  border: 1px solid var(--color-border);
  border-radius: 7px;
  padding: 7px 10px;
  font-size: 12px;
  font-family: ui-monospace, monospace;
  color: var(--color-text-muted);
  background: var(--color-surface);
  min-width: 0;
}
.share-copy-btn {
  flex-shrink: 0;
}
.export-error {
  font-size: 12px;
  color: var(--color-red);
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  padding: 6px 10px;
  margin: 0;
}
</style>
