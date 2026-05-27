import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ColumnInfo, ColumnType, DatasetPreview } from '../types/dataset'

const STORAGE_KEY = 'ra_dataset'
const TTL_MS = 30 * 60 * 1000

interface PersistedDataset {
  filename: string
  rowCount: number
  columns: ColumnInfo[]
  datasetContext: 'survey' | 'generic'
  warnings: string[]
  overrides: [string, ColumnType][]
  expiry: number
}

export const useDatasetStore = defineStore('dataset', () => {
  const filename = ref<string | null>(null)
  const rowCount = ref<number>(0)
  const columns = ref<ColumnInfo[]>([])
  const columnTypeOverrides = ref<Map<string, ColumnType>>(new Map())
  const datasetContext = ref<'survey' | 'generic'>('generic')
  const warnings = ref<string[]>([])

  const isLoaded = computed(() => filename.value !== null)

  function persistDataset() {
    if (!filename.value) return
    const data: PersistedDataset = {
      filename: filename.value,
      rowCount: rowCount.value,
      columns: columns.value,
      datasetContext: datasetContext.value,
      warnings: warnings.value,
      overrides: [...columnTypeOverrides.value.entries()],
      expiry: Date.now() + TTL_MS,
    }
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  }

  function restoreDataset(): boolean {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return false
    try {
      const data: PersistedDataset = JSON.parse(raw)
      if (Date.now() > data.expiry) {
        sessionStorage.removeItem(STORAGE_KEY)
        return false
      }
      filename.value = data.filename
      rowCount.value = data.rowCount
      columns.value = data.columns
      datasetContext.value = data.datasetContext
      warnings.value = data.warnings
      columnTypeOverrides.value = new Map(data.overrides)
      return true
    } catch {
      sessionStorage.removeItem(STORAGE_KEY)
      return false
    }
  }

  function load(preview: DatasetPreview) {
    filename.value = preview.filename
    rowCount.value = preview.row_count
    columns.value = preview.columns
    datasetContext.value = preview.dataset_context
    warnings.value = preview.warnings
    columnTypeOverrides.value = new Map()
    persistDataset()
  }

  function overrideColumnType(columnName: string, type: ColumnType) {
    columnTypeOverrides.value.set(columnName, type)
    persistDataset()
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
    sessionStorage.removeItem(STORAGE_KEY)
  }

  return {
    filename, rowCount, columns, columnTypeOverrides, datasetContext, warnings,
    isLoaded, load, overrideColumnType, effectiveColumnType,
    clearDataset, persistDataset, restoreDataset,
  }
})
