<script setup lang="ts">
import { ref, computed } from 'vue'
import { useApi } from '../../composables/useApi'
import type { ColumnInfo, DatasetPreview } from '../../types/dataset'

const props = defineProps<{ sessionId: string; columns: ColumnInfo[] }>()
const emit = defineEmits<{ (e: 'updated', preview: DatasetPreview): void }>()

const api = useApi()

const numericColumns = computed(() => props.columns.filter(c => c.inferred_type === 'ordinal' || c.inferred_type === 'continuous'))
const selected = ref<string[]>([])
const minValue = ref(1)
const maxValue = ref(5)
const suffix = ref('_r')
const overwrite = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)

async function apply() {
  if (selected.value.length === 0) return
  loading.value = true
  error.value = null
  message.value = null
  try {
    const preview = await api.reverseScore(props.sessionId, selected.value, minValue.value, maxValue.value, suffix.value, overwrite.value)
    message.value = preview.warnings[0] ?? 'Applied.'
    emit('updated', preview)
    selected.value = []
  } catch (e: any) {
    error.value = e.message ?? 'Could not reverse-score the selected columns.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="panel">
    <p class="panel-sub">
      Flip the scale of negatively-worded scale items (e.g. Likert 1–5) so all items point the same direction
      before computing a composite score.
    </p>

    <div class="field-group">
      <label class="field-label">Items to reverse-score</label>
      <div class="checkbox-list">
        <label v-for="col in numericColumns" :key="col.name" class="checkbox-item">
          <input type="checkbox" :value="col.name" v-model="selected" />
          {{ col.name }}
        </label>
      </div>
    </div>

    <div class="range-row">
      <div class="field-group">
        <label class="field-label">Scale minimum</label>
        <input v-model.number="minValue" type="number" class="text-input small" />
      </div>
      <div class="field-group">
        <label class="field-label">Scale maximum</label>
        <input v-model.number="maxValue" type="number" class="text-input small" />
      </div>
      <div class="field-group">
        <label class="field-label">New column suffix</label>
        <input v-model="suffix" class="text-input small" />
      </div>
    </div>

    <label class="checkbox-item">
      <input type="checkbox" v-model="overwrite" />
      Overwrite if the resulting column name already exists
    </label>

    <div v-if="error" class="error-msg" role="alert">{{ error }}</div>
    <div v-if="message" class="success-msg">{{ message }}</div>

    <button class="btn-primary" :disabled="selected.length === 0 || minValue >= maxValue || loading" @click="apply">
      <span v-if="loading">Applying…</span>
      <span v-else>Apply</span>
    </button>
  </div>
</template>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 16px; }
.panel-sub { color: var(--color-text-muted); font-size: 13px; margin: 0; }
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-label { font-size: 13px; font-weight: 600; color: var(--color-text-muted); }
.checkbox-list { display: flex; flex-direction: column; gap: 6px; max-height: 180px; overflow-y: auto; }
.checkbox-item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.range-row { display: flex; gap: 16px; }
.text-input {
  border: 1px solid var(--color-border); border-radius: 8px; padding: 8px 10px;
  font-size: 13px; background: var(--color-bg); color: var(--color-text);
}
.text-input.small { width: 90px; }
.error-msg {
  background: #fef2f2; border: 1px solid #fecaca; color: var(--color-red);
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
