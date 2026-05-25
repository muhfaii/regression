<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAnalysisStore } from '../stores/analysis'
import { useDatasetStore } from '../stores/dataset'
import { useSessionStore } from '../stores/session'
import { useResultsStore } from '../stores/results'
import { useApi } from '../composables/useApi'
import type { ColumnType } from '../types/dataset'

const router = useRouter()
const analysis = useAnalysisStore()
const dataset = useDatasetStore()
const session = useSessionStore()
const results = useResultsStore()
const api = useApi()

const error = ref<string | null>(null)

const test = computed(() => analysis.selectedTest)
const columns = computed(() => dataset.columns)

function effectiveType(colName: string): ColumnType {
  return dataset.effectiveColumnType(colName)
}

const TYPE_COLOR: Record<ColumnType, string> = {
  continuous: '#3b82f6',
  categorical: '#16a34a',
  ordinal: '#d97706',
  date: '#6b7280',
}

function updateSlot(key: string, value: string | string[]) {
  analysis.updateConfig({ [key]: value })
}

function handleMultiSelect(key: string, event: Event) {
  const select = event.target as HTMLSelectElement
  const selected = Array.from(select.selectedOptions).map(o => o.value)
  updateSlot(key, selected)
}

async function runAnalysis() {
  if (!session.sessionId || !test.value) return
  error.value = null
  analysis.setRunning(true)
  try {
    const result = await api.runAnalysis({
      session_id: session.sessionId,
      test_key: test.value.key,
      config: analysis.config,
      options: analysis.options,
    }) as import('../types/results').AnalysisResult
    results.addResult(result)
    router.push('/results')
  } catch (e: any) {
    error.value = e.message ?? 'Analysis failed.'
  } finally {
    analysis.setRunning(false)
  }
}
</script>

<template>
  <div v-if="!test" class="no-test">Select a test from the sidebar.</div>

  <div v-else class="config-panel">
    <h2 class="test-title">{{ test.name }}</h2>
    <p class="test-tooltip">{{ test.tooltip }}</p>

    <div class="slots">
      <div v-for="slot in test.slots" :key="slot.key" class="slot">
        <label class="slot-label">
          {{ slot.label }}
          <span v-if="slot.required_type !== 'any'" class="type-hint" :style="{ color: TYPE_COLOR[slot.required_type as ColumnType] }">
            {{ slot.required_type }}
          </span>
        </label>

        <!-- Multi-select -->
        <select
          v-if="slot.multiple"
          multiple
          class="var-select"
          :size="Math.min(columns.length, 6)"
          @change="handleMultiSelect(slot.key, $event)"
        >
          <option v-for="col in columns" :key="col.name" :value="col.name">
            {{ col.name }}
            ({{ effectiveType(col.name) }})
          </option>
        </select>

        <!-- Single select -->
        <select
          v-else
          class="var-select single"
          :value="(analysis.config[slot.key] as string) ?? ''"
          @change="updateSlot(slot.key, ($event.target as HTMLSelectElement).value)"
        >
          <option value="">— select —</option>
          <option v-for="col in columns" :key="col.name" :value="col.name">
            {{ col.name }} ({{ effectiveType(col.name) }})
          </option>
        </select>
      </div>
    </div>

    <!-- Options -->
    <div class="options">
      <label class="option-toggle">
        <input type="checkbox" v-model="analysis.options.assumption_checks" />
        Run assumption checks
      </label>
      <label class="option-toggle">
        <input type="checkbox" v-model="analysis.options.effect_size" />
        Calculate effect size
      </label>
      <label class="option-toggle">
        <input type="checkbox" v-model="analysis.options.post_hoc" />
        Post-hoc tests (where applicable)
      </label>
    </div>

    <div v-if="error" class="error-msg" role="alert">{{ error }}</div>

    <button
      class="run-btn"
      :disabled="!analysis.requiredSlotsFilled || analysis.isRunning"
      @click="runAnalysis"
    >
      <span v-if="analysis.isRunning">Running…</span>
      <span v-else>Run analysis</span>
    </button>

    <p v-if="!analysis.requiredSlotsFilled" class="validation-msg">
      Select all required variables to run.
    </p>
  </div>
</template>

<style scoped>
.no-test { color: var(--color-text-muted); font-size: 14px; }
.config-panel { display: flex; flex-direction: column; gap: 24px; max-width: 480px; }
.test-title { font-size: 20px; }
.test-tooltip { font-size: 13px; color: var(--color-text-muted); }
.slots { display: flex; flex-direction: column; gap: 16px; }
.slot { display: flex; flex-direction: column; gap: 6px; }
.slot-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.type-hint { font-size: 11px; font-weight: 700; text-transform: uppercase; }
.var-select {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 6px 8px;
  font-size: 13px;
  background: var(--color-bg);
  width: 100%;
}
.var-select:focus { outline: 2px solid var(--color-primary); }
.var-select.single { height: 36px; }
.options { display: flex; flex-direction: column; gap: 10px; }
.option-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}
.run-btn {
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 12px 24px;
  font-size: 15px;
  font-weight: 600;
  transition: background 0.15s;
}
.run-btn:hover:not(:disabled) { background: var(--color-primary-hover); }
.run-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.validation-msg { font-size: 12px; color: var(--color-text-muted); margin-top: -16px; }
.error-msg {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: var(--color-red);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
}
</style>
