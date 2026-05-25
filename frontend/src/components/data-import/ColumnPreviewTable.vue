<script setup lang="ts">
import type { ColumnInfo, ColumnType } from '../../types/dataset'

const props = defineProps<{ columns: ColumnInfo[] }>()
const emit = defineEmits<{ (e: 'type-change', name: string, type: ColumnType): void }>()

const TYPE_OPTIONS: ColumnType[] = ['continuous', 'categorical', 'ordinal', 'date']

const TYPE_COLORS: Record<ColumnType, string> = {
  continuous: '#3b82f6',
  categorical: '#16a34a',
  ordinal: '#d97706',
  date: '#6b7280',
}

function effectiveType(col: ColumnInfo): ColumnType {
  return col.override_type ?? col.inferred_type
}
</script>

<template>
  <div class="preview-table-wrap">
    <table class="preview-table">
      <thead>
        <tr>
          <th>Column</th>
          <th>Type</th>
          <th>Missing</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="col in columns" :key="col.name">
          <td class="col-name">{{ col.name }}</td>
          <td>
            <select
              class="type-select"
              :value="effectiveType(col)"
              :style="{ color: TYPE_COLORS[effectiveType(col)] }"
              @change="emit('type-change', col.name, ($event.target as HTMLSelectElement).value as ColumnType)"
            >
              <option v-for="t in TYPE_OPTIONS" :key="t" :value="t">{{ t }}</option>
            </select>
          </td>
          <td class="missing" :class="{ warn: col.missing_count > 0 }">
            {{ col.missing_count > 0 ? `${col.missing_count} (${col.missing_pct}%)` : '—' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.preview-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--color-border);
  border-radius: 8px;
}
.preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.preview-table th {
  text-align: left;
  padding: 8px 12px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  font-weight: 600;
  color: var(--color-text-muted);
}
.preview-table td {
  padding: 7px 12px;
  border-bottom: 1px solid var(--color-border);
}
.preview-table tr:last-child td { border-bottom: none; }
.col-name { font-weight: 500; }
.type-select {
  border: none;
  background: none;
  font-weight: 600;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}
.type-select:focus { outline: 2px solid var(--color-primary); border-radius: 3px; }
.missing { color: var(--color-text-muted); }
.missing.warn { color: var(--color-amber); font-weight: 500; }
</style>
