<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from '../composables/useApi'
import SharedResultCard from '../components/results/SharedResultCard.vue'

const route = useRoute()
const api = useApi()

const bundle = ref<{ filename: string; results: Record<string, any>[] } | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  const token = route.params.token as string
  try {
    bundle.value = await api.getSharedSession(token)
  } catch (e: any) {
    error.value = e.message ?? 'Could not load shared results.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="share-view">
    <div v-if="loading" class="state-msg">Loading shared results…</div>

    <div v-else-if="error" class="state-msg error-msg" role="alert">
      {{ error }}
    </div>

    <div v-else-if="bundle">
      <div class="share-header">
        <span class="share-badge">Shared session</span>
        <h1 class="dataset-title">{{ bundle.filename }}</h1>
        <p class="dataset-meta">{{ bundle.results.length }} result(s)</p>
      </div>

      <div
        v-for="(result, i) in bundle.results"
        :key="result.result_id ?? i"
        class="result-block"
      >
        <SharedResultCard :result="result" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.share-view {
  max-width: 780px;
  margin: 0 auto;
  padding: 48px 24px;
}
.state-msg {
  text-align: center;
  color: var(--color-text-muted);
  margin-top: 80px;
  font-size: 14px;
}
.error-msg { color: var(--color-red); }
.share-header { margin-bottom: 32px; }
.share-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--color-primary);
  background: #ede9fe;
  border-radius: 99px;
  padding: 2px 10px;
  width: fit-content;
  margin-bottom: 12px;
}
.dataset-title { font-size: 24px; margin: 0 0 4px; }
.dataset-meta { font-size: 13px; color: var(--color-text-muted); margin: 0; }
.result-block {
  padding: 28px 0;
  border-top: 1px solid var(--color-border);
}
</style>
