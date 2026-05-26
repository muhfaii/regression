<script setup lang="ts">
import type { TestDefinition } from '../../types/analysis'

defineProps<{
  test: TestDefinition
  reason: string
  configureLabel?: string
}>()

const emit = defineEmits<{
  configure: []
  reset: []
}>()
</script>

<template>
  <div class="recommendation-card">
    <div class="rec-tag">Recommended test</div>
    <h2 class="rec-test-name">{{ test.name }}</h2>
    <p class="rec-reason">{{ reason }}</p>

    <div class="rec-assumptions">
      <div class="rec-section-label">Assumption checks that will run:</div>
      <p class="rec-assumption-note">Normality, equal variances, and other relevant checks will run automatically — no setup needed.</p>
    </div>

    <div class="rec-actions">
      <button class="btn-primary" @click="emit('configure')">{{ configureLabel ?? 'Configure &amp; run →' }}</button>
      <button class="btn-ghost" @click="emit('reset')">Start over</button>
    </div>
  </div>
</template>

<style scoped>
.recommendation-card {
  border: 1px solid var(--color-border); border-radius: 16px; padding: 36px;
  display: flex; flex-direction: column; gap: 16px; width: 100%; max-width: 560px; margin: 0 auto;
}
.rec-tag { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--color-primary); }
.rec-test-name { font-size: 24px; margin: 0; }
.rec-reason { font-size: 14px; color: var(--color-text-muted); line-height: 1.6; margin: 0; }
.rec-assumptions { background: var(--color-surface); border-radius: 8px; padding: 14px 16px; }
.rec-section-label { font-size: 12px; font-weight: 700; color: var(--color-text-muted); margin-bottom: 6px; }
.rec-assumption-note { font-size: 13px; color: var(--color-text-muted); margin: 0; }
.rec-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.btn-primary {
  background: var(--color-primary); color: #fff; border: none; border-radius: 8px;
  padding: 11px 22px; font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.15s;
}
.btn-primary:hover { background: var(--color-primary-hover); }
.btn-ghost {
  background: none; border: 1px solid var(--color-border); border-radius: 8px;
  padding: 10px 16px; font-size: 14px; color: var(--color-text-muted); cursor: pointer;
}
.btn-ghost:hover { border-color: var(--color-text-muted); color: var(--color-text); }
</style>
