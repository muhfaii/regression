<script setup lang="ts">
import { ref } from 'vue'
import { useApi } from '../../composables/useApi'
import type { ColumnInfo, DatasetPreview } from '../../types/dataset'

const props = defineProps<{ sessionId: string; columns: ColumnInfo[] }>()
const emit = defineEmits<{ (e: 'updated', preview: DatasetPreview): void }>()

const api = useApi()

type Mode = 'recode' | 'compute'
const mode = ref<Mode>('recode')
const loading = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)

// --- Recode state ---
const sourceColumn = ref('')
const recodeNewName = ref('')
type MappingRow = { from: string; to: string }
const mappingRows = ref<MappingRow[]>([{ from: '', to: '' }])
const defaultValue = ref('')
const recodeOverwrite = ref(false)

function addMappingRow() {
  mappingRows.value.push({ from: '', to: '' })
}
function removeMappingRow(i: number) {
  mappingRows.value.splice(i, 1)
}

async function applyRecode() {
  const mapping: Record<string, string> = {}
  for (const row of mappingRows.value) {
    if (row.from.trim() !== '') mapping[row.from.trim()] = row.to
  }
  if (!sourceColumn.value || !recodeNewName.value || Object.keys(mapping).length === 0) return

  loading.value = true
  error.value = null
  message.value = null
  try {
    const preview = await api.recodeColumn(
      props.sessionId, sourceColumn.value, recodeNewName.value, mapping,
      { default: defaultValue.value || undefined, overwrite: recodeOverwrite.value },
    )
    message.value = preview.warnings[0] ?? 'Applied.'
    emit('updated', preview)
    recodeNewName.value = ''
    mappingRows.value = [{ from: '', to: '' }]
  } catch (e: any) {
    error.value = e.message ?? 'Could not recode column.'
  } finally {
    loading.value = false
  }
}

// --- Compute state ---
const computeNewName = ref('')
const expression = ref('')
const computeOverwrite = ref(false)

async function applyCompute() {
  if (!computeNewName.value || !expression.value.trim()) return
  loading.value = true
  error.value = null
  message.value = null
  try {
    const preview = await api.computeColumn(props.sessionId, computeNewName.value, expression.value, computeOverwrite.value)
    message.value = preview.warnings[0] ?? 'Applied.'
    emit('updated', preview)
    computeNewName.value = ''
    expression.value = ''
  } catch (e: any) {
    error.value = e.message ?? 'Could not compute column. Check your expression.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="panel">
    <div class="mode-tabs">
      <button class="mode-tab" :class="{ active: mode === 'recode' }" @click="mode = 'recode'">Recode values</button>
      <button class="mode-tab" :class="{ active: mode === 'compute' }" @click="mode = 'compute'">Compute new variable</button>
    </div>

    <template v-if="mode === 'recode'">
      <p class="panel-sub">Map old values in a column to new values (e.g. "Male" → 1, "Female" → 2).</p>

      <div class="field-group">
        <label class="field-label">Source column</label>
        <select v-model="sourceColumn" class="select">
          <option value="" disabled>Select a column…</option>
          <option v-for="c in columns" :key="c.name" :value="c.name">{{ c.name }}</option>
        </select>
      </div>

      <div class="field-group">
        <label class="field-label">New column name</label>
        <input v-model="recodeNewName" class="text-input" placeholder="e.g. gender_code" />
      </div>

      <div class="field-group">
        <label class="field-label">Value mapping</label>
        <div v-for="(row, i) in mappingRows" :key="i" class="mapping-row">
          <input v-model="row.from" class="text-input" placeholder="Old value" />
          <span class="arrow">→</span>
          <input v-model="row.to" class="text-input" placeholder="New value" />
          <button class="btn-icon" type="button" @click="removeMappingRow(i)" aria-label="Remove row">×</button>
        </div>
        <button class="btn-ghost-sm" type="button" @click="addMappingRow">+ Add mapping</button>
      </div>

      <div class="field-group">
        <label class="field-label">Default for unmapped values (optional)</label>
        <input v-model="defaultValue" class="text-input" placeholder="Leave blank to keep original value" />
      </div>

      <label class="checkbox-item">
        <input type="checkbox" v-model="recodeOverwrite" />
        Overwrite if column name already exists
      </label>

      <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
      <div v-if="message" class="success-msg">{{ message }}</div>

      <button class="btn-primary" :disabled="!sourceColumn || !recodeNewName || loading" @click="applyRecode">
        <span v-if="loading">Applying…</span>
        <span v-else>Apply</span>
      </button>
    </template>

    <template v-else>
      <p class="panel-sub">
        Write an arithmetic expression using existing column names, e.g. <code>item1 + item2 + item3</code>
        or <code>(income - colmin(income)) / (colmax(income) - colmin(income))</code>.
      </p>

      <div class="field-group">
        <label class="field-label">New column name</label>
        <input v-model="computeNewName" class="text-input" placeholder="e.g. scale_total" />
      </div>

      <div class="field-group">
        <label class="field-label">Expression</label>
        <input v-model="expression" class="text-input mono" placeholder="item1 + item2 + item3" />
      </div>

      <label class="checkbox-item">
        <input type="checkbox" v-model="computeOverwrite" />
        Overwrite if column name already exists
      </label>

      <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
      <div v-if="message" class="success-msg">{{ message }}</div>

      <button class="btn-primary" :disabled="!computeNewName || !expression.trim() || loading" @click="applyCompute">
        <span v-if="loading">Computing…</span>
        <span v-else>Apply</span>
      </button>
    </template>
  </div>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 16px; }
.panel-sub { color: var(--color-text-muted); font-size: 13px; margin: 0; }
.panel-sub code { background: var(--color-surface); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.mode-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); }
.mode-tab {
  background: none; border: none; border-bottom: 2px solid transparent;
  padding: 8px 12px; font-size: 13px; font-weight: 500; color: var(--color-text-muted);
  cursor: pointer; margin-bottom: -1px;
}
.mode-tab.active { color: var(--color-primary); border-bottom-color: var(--color-primary); font-weight: 600; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 600; color: var(--color-text-muted); }
.select, .text-input {
  border: 1px solid var(--color-border); border-radius: 8px; padding: 8px 10px;
  font-size: 13px; background: var(--color-bg); color: var(--color-text);
}
.text-input.mono { font-family: monospace; }
.mapping-row { display: flex; align-items: center; gap: 8px; }
.mapping-row .text-input { flex: 1; }
.arrow { color: var(--color-text-muted); }
.btn-icon {
  border: none; background: none; color: var(--color-text-muted);
  font-size: 16px; cursor: pointer; padding: 0 6px;
}
.btn-icon:hover { color: var(--color-red); }
.btn-ghost-sm {
  align-self: flex-start; border: none; background: none; color: var(--color-primary);
  font-size: 13px; font-weight: 500; cursor: pointer; padding: 4px 0;
}
.checkbox-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.error-msg {
  background: var(--color-red-bg); border: 1px solid var(--color-red-border); color: var(--color-red);
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
