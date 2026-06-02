import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ColumnInfo, ColumnType, DatasetPreview } from '../types/dataset'

export const useDatasetStore = defineStore('dataset', () => {
  const filename = ref<string | null>(null)
  const rowCount = ref<number>(0)
  const columns = ref<ColumnInfo[]>([])
  const columnTypeOverrides = ref<Map<string, ColumnType>>(new Map())
  const datasetContext = ref<'survey' | 'generic'>('generic')
  const warnings = ref<string[]>([])

  const isLoaded = computed(() => filename.value !== null)

  function load(preview: DatasetPreview) {
    filename.value = preview.filename
    rowCount.value = preview.row_count
    columns.value = preview.columns
    datasetContext.value = preview.dataset_context
    warnings.value = preview.warnings
    columnTypeOverrides.value = new Map()
  }

  function overrideColumnType(columnName: string, type: ColumnType) {
    columnTypeOverrides.value.set(columnName, type)
  }

  function effectiveColumnType(columnName: string): ColumnType {
    return columnTypeOverrides.value.get(columnName)
      ?? columns.value.find(c => c.name === columnName)?.inferred_type
      ?? 'continuous'
  }

  function clearDataset() {
    filename.value = null
    rowCount.value = 0
    columns.value = []
    columnTypeOverrides.value = new Map()
    warnings.value = []
  }

  return {
    filename, rowCount, columns, columnTypeOverrides, datasetContext, warnings,
    isLoaded, load, overrideColumnType, effectiveColumnType,
    clearDataset,
  }
})
