import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDatasetStore } from '../stores/dataset'
import type { DatasetPreview } from '../types/dataset'

const mockPreview: DatasetPreview = {
  session_id: 'sess-1',
  filename: 'test.csv',
  row_count: 100,
  columns: [
    { name: 'age', raw_dtype: 'int64', inferred_type: 'continuous', missing_count: 0, missing_pct: 0, has_masked_numeric: false },
    { name: 'group', raw_dtype: 'object', inferred_type: 'categorical', missing_count: 0, missing_pct: 0, has_masked_numeric: false },
  ],
  dataset_context: 'generic',
  warnings: [],
}

beforeEach(() => {
  setActivePinia(createPinia())
})

describe('useDatasetStore', () => {
  it('load() sets filename, rowCount, columns, and datasetContext', () => {
    const store = useDatasetStore()
    store.load(mockPreview)

    expect(store.filename).toBe('test.csv')
    expect(store.rowCount).toBe(100)
    expect(store.columns).toHaveLength(2)
    expect(store.datasetContext).toBe('generic')
    expect(store.isLoaded).toBe(true)
  })

  it('overrideColumnType() overrides effective type', () => {
    const store = useDatasetStore()
    store.load(mockPreview)
    store.overrideColumnType('age', 'ordinal')

    expect(store.effectiveColumnType('age')).toBe('ordinal')
  })

  it('clearDataset() resets all state', () => {
    const store = useDatasetStore()
    store.load(mockPreview)
    expect(store.isLoaded).toBe(true)

    store.clearDataset()
    expect(store.isLoaded).toBe(false)
    expect(store.filename).toBeNull()
    expect(store.columns).toHaveLength(0)
  })

  it('effectiveColumnType returns inferred type when no override set', () => {
    const store = useDatasetStore()
    store.load(mockPreview)

    expect(store.effectiveColumnType('age')).toBe('continuous')
    expect(store.effectiveColumnType('group')).toBe('categorical')
  })
})
