<script setup lang="ts">
import { ref, computed } from 'vue'
import { useApi } from '../../composables/useApi'
import type { ColumnInfo, DatasetPreview } from '../../types/dataset'

const props = defineProps<{ sessionId: string; columns: ColumnInfo[] }>()
const emit = defineEmits<{ (e: 'updated', preview: DatasetPreview): void }>()

const api = useApi()

type Strategy = 'listwise' | 'mean' | 'median' | 'mode' | 'constant'

const columnsWithMissing = computed(() => props.columns.filter(c => c.missing_count > 0))
const selected = ref<string[]>([])
const strategy = ref<Strategy>('listwise')
const constantValue = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)

const strategyHelp: Record<Strategy, string> = {
  listwise: 'Removes entire rows where the selected column(s) are missing. Safest when missingness is small and random.',
  mean: 'Fills missing values with the column average. Numeric columns only — can understate variability.',
  median: 'Fills missing values with the column median. Numeric columns only — more robust to outliers than mean.',
  mode: 'Fills missing values with the most common value. Works for categorical or numeric columns.',
  constant: 'Fills missing values with a fixed value you provide (e.g. a "missing" code).',
}

async function apply() {
  if (selected.value.length === 0) return
  loading.value = true
  error.value = null
  message.value = null
  try {
    const preview = await api.applyMissingData(
      props.sessionId,
      selected.value,
      strategy.value,
      strategy.value === 'constant' ? constantValue.value : undefined,
    )
    message.value = preview.warnings[0] ?? 'Applied.'
    emit('updated', preview)
    selected.value = []
  } catch (e: any) {
    error.value = e.message ?? 'Could not apply missing-data strategy.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="panel">
    <p class="panel-sub">Choose which columns to clean and how to handle their missing values.</p>

    <div v-if="columnsWithMissing.length === 0" class="empty-state">
      No columns with missing values were detected.
    </div>

    <template v-else>
      <div class="field-group">
        <label class="field-label">Columns with missing data</label>
        <div class="checkbox-list">
          <label v-for="col in columnsWithMissing" :key="col.name" class="checkbox-item">
            <input type="checkbox" :value="col.name" v-model="selected" />
            {{ col.name }} <span class="muted">({{ col.missing_count }} missing, {{ col.missing_pct }}%)</span>
          </label>
        </div>
      </div>

      <div class="field-group">
        <label class="field-label">Strategy</label>
        <select v-model="strategy" class="select">
          <option value="listwise">Remove rows (listwise deletion)</option>
          <option value="mean">Fill with mean</option>
          <option value="median">Fill with median</option>
          <option value="mode">Fill with mode (most common value)</option>
          <option value="constant">Fill with a constant value</option>
        </select>
        <p class="help-text">{{ strategyHelp[strategy] }}</p>
      </div>

      <div v-if="strategy === 'constant'" class="field-group">
        <label class="field-label">Constant value</label>
        <input v-model="constantValue" class="text-input" placeholder="e.g. 0 or Unknown" />
      </div>

      <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
      <div v-if="message" class="success-msg">{{ message }}</div>

      <button
        class="btn-primary"
        :disabled="selected.length === 0 || loading || (strategy === 'constant' && !constantValue)"
        @click="apply"
      >
        <span v-if="loading">Applying…</span>
        <span v-else>Apply</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 16px; }
.panel-sub { color: var(--color-text-muted); font-size: 13px; margin: 0; }
.empty-state { color: var(--color-text-muted); font-size: 13px; padding: 16px; text-align: center; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 600; color: var(--color-text-muted); }
.checkbox-list { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; }
.checkbox-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.muted { color: var(--color-text-muted); font-size: 12px; }
.select, .text-input {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  background: var(--color-bg);
  color: var(--color-text);
}
.help-text { font-size: 12px; color: var(--color-text-muted); margin: 0; }
.error-msg {
  background: #fef2f2; border: 1px solid #fecaca; color: var(--color-red);
  border-radius: 8px; padding: 10px 14px; font-size: 13px;
}
.success-msg {
  background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d;
  border-radius: 8px; padding: 10px 14px; font-size: 13px;
}
.btn-primary {
  align-self: flex-start;
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
