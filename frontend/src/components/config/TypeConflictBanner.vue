<script setup lang="ts">
import type { ColumnType } from '../../types/dataset'
import { useDatasetStore } from '../../stores/dataset'

interface Conflict {
  slot: string
  column: string
  required_type: string
  actual_type: string
}

const props = defineProps<{ conflicts: Conflict[] }>()
const emit = defineEmits<{ (e: 'type-change', column: string, type: ColumnType): void }>()

const dataset = useDatasetStore()

const TYPE_OPTIONS: ColumnType[] = ['continuous', 'categorical', 'ordinal', 'date']

function handleOverride(column: string, event: Event) {
  const type = (event.target as HTMLSelectElement).value as ColumnType
  dataset.overrideColumnType(column, type)
  emit('type-change', column, type)
}
</script>

<template>
  <div v-if="conflicts.length" class="conflict-banner" role="alert">
    <p class="banner-title">Column type needs adjustment</p>
    <div v-for="c in conflicts" :key="c.slot + c.column" class="conflict-row">
      <span class="conflict-label">
        <strong>{{ c.column }}</strong> needs to be
        <span class="type-chip required">{{ c.required_type }}</span>
        but is currently
        <span class="type-chip actual">{{ c.actual_type }}</span>
      </span>
      <select class="type-select" :value="dataset.effectiveColumnType(c.column)" @change="handleOverride(c.column, $event)">
        <option v-for="t in TYPE_OPTIONS" :key="t" :value="t">{{ t }}</option>
      </select>
    </div>
  </div>
</template>

<style scoped>
.conflict-banner {
  background: var(--color-amber-bg);
  border: 1px solid var(--color-amber-border);
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.banner-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-amber);
  margin: 0;
}
.conflict-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.conflict-label {
  font-size: 13px;
  color: var(--color-text);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.type-chip {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  text-transform: uppercase;
}
.type-chip.required { background: var(--color-green-bg); color: var(--color-green); }
.type-chip.actual { background: var(--color-red-bg); color: var(--color-red); }
.type-select {
  border: 1px solid var(--color-amber-border);
  border-radius: 6px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 12px;
  font-weight: 600;
  padding: 4px 8px;
  flex-shrink: 0;
  cursor: pointer;
}
</style>
