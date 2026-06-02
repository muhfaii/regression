<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'

const props = defineProps<{ conversationId?: string }>()
const emit = defineEmits<{ (e: 'imported', data: unknown): void }>()

const api = useApi()
const samples = ref<{ id: string; label: string; description: string }[]>([])
const loadingId = ref<string | null>(null)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    samples.value = await api.listSamples()
  } catch {
    // Non-fatal: grid stays empty
  }
})

async function loadSample(id: string) {
  loadingId.value = id
  error.value = null
  try {
    const data = await api.loadSample(id, props.conversationId)
    emit('imported', data)
  } catch (e: any) {
    error.value = e.message ?? 'Failed to load sample.'
  } finally {
    loadingId.value = null
  }
}
</script>

<template>
  <div class="sample-grid">
    <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
    <div class="grid">
      <button
        v-for="s in samples"
        :key="s.id"
        class="sample-card"
        :disabled="loadingId === s.id"
        @click="loadSample(s.id)"
      >
        <span class="sample-label">{{ s.label }}</span>
        <span class="sample-desc">{{ s.description }}</span>
        <span v-if="loadingId === s.id" class="loading-dot">Loading…</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.sample-grid { display: flex; flex-direction: column; gap: 12px; }
.grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.sample-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.sample-card:hover:not(:disabled) {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 12%, transparent);
}
.sample-card:disabled { opacity: 0.6; cursor: not-allowed; }
.sample-label { font-size: 13px; font-weight: 600; color: var(--color-text); }
.sample-desc { font-size: 12px; color: var(--color-text-muted); line-height: 1.4; }
.loading-dot { font-size: 11px; color: var(--color-primary); margin-top: 4px; }
.error-msg {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: var(--color-red);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
}
</style>
