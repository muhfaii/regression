<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useDatasetStore } from '../stores/dataset'
import { useSessionStore } from '../stores/session'

const router = useRouter()
const dataset = useDatasetStore()
const session = useSessionStore()

function choose(mode: 'guide' | 'browse') {
  session.setMode(mode)
  router.push(mode === 'guide' ? '/guide' : '/browse')
}
</script>

<template>
  <div class="home-view">
    <p class="dataset-label">Dataset: <strong>{{ dataset.filename }}</strong></p>
    <h1 class="home-title">How would you like to analyse your data?</h1>

    <div class="mode-cards">
      <button class="mode-card" @click="choose('guide')">
        <div class="mode-icon">🧭</div>
        <div class="mode-label">Guide me</div>
        <div class="mode-badge">Recommended for students</div>
        <p class="mode-desc">Answer 4 quick questions and we'll recommend the right statistical test for your data.</p>
      </button>

      <button class="mode-card" @click="choose('browse')">
        <div class="mode-icon">📋</div>
        <div class="mode-label">Browse tests</div>
        <p class="mode-desc">Pick a test directly from the full list of available analyses.</p>
      </button>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 64px 24px;
}
.dataset-label {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 16px;
}
.home-title {
  font-size: 22px;
  margin-bottom: 40px;
  text-align: center;
}
.mode-cards {
  display: flex;
  gap: 24px;
  width: 100%;
  max-width: 640px;
}
.mode-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
  border: 2px solid var(--color-border);
  border-radius: 12px;
  padding: 28px 24px;
  background: var(--color-bg);
  transition: border-color 0.15s, box-shadow 0.15s;
  cursor: pointer;
}
.mode-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 4px 16px rgba(79,70,229,0.1);
}
.mode-icon { font-size: 28px; margin-bottom: 12px; }
.mode-label {
  font-size: 17px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 6px;
}
.mode-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-primary);
  background: #ede9fe;
  border-radius: 99px;
  padding: 2px 8px;
  margin-bottom: 12px;
}
.mode-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  line-height: 1.5;
}
</style>
