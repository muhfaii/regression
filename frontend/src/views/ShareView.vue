<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useApi } from '../composables/useApi'
import SharedResultCard from '../components/results/SharedResultCard.vue'

const route = useRoute()
const api = useApi()

const result = ref<Record<string, any> | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

onMounted(async () => {
  const token = route.params.token as string
  try {
    result.value = await api.getSharedResult(token)
  } catch (e: any) {
    error.value = e.message ?? 'Could not load shared result.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="share-view">
    <div v-if="loading" class="state-msg">Loading shared result…</div>

    <div v-else-if="error" class="state-msg error-msg" role="alert">
      {{ error }}
    </div>

    <div v-else-if="result">
      <span class="share-badge">Shared result</span>
      <SharedResultCard :result="result" />
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
.share-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--color-primary);
  background: var(--color-accent-tint);
  border-radius: 99px;
  padding: 2px 10px;
  width: fit-content;
  margin-bottom: 20px;
}
</style>
