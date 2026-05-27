import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDatasetStore } from '../stores/dataset'
import type { DatasetPreview } from '../types/dataset'

const STORAGE_KEY = 'ra_dataset'

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
  sessionStorage.clear()
  vi.restoreAllMocks()
})

describe('useDatasetStore', () => {
  it('load() writes to sessionStorage', () => {
    const store = useDatasetStore()
    store.load(mockPreview)

    const raw = sessionStorage.getItem(STORAGE_KEY)
    expect(raw).not.toBeNull()
    const parsed = JSON.parse(raw!)
    expect(parsed.filename).toBe('test.csv')
    expect(parsed.rowCount).toBe(100)
    expect(parsed.expiry).toBeGreaterThan(Date.now())
  })

  it('restoreDataset() restores filename, rowCount, columns, and datasetContext', () => {
    const store = useDatasetStore()
    store.load(mockPreview)

    setActivePinia(createPinia())
    const freshStore = useDatasetStore()
    const restored = freshStore.restoreDataset()

    expect(restored).toBe(true)
    expect(freshStore.filename).toBe('test.csv')
    expect(freshStore.rowCount).toBe(100)
    expect(freshStore.columns).toHaveLength(2)
    expect(freshStore.datasetContext).toBe('generic')
    expect(freshStore.isLoaded).toBe(true)
  })

  it('overrideColumnType() persists override; restoreDataset restores it', () => {
    const store = useDatasetStore()
    store.load(mockPreview)
    store.overrideColumnType('age', 'ordinal')

    setActivePinia(createPinia())
    const freshStore = useDatasetStore()
    freshStore.restoreDataset()

    expect(freshStore.effectiveColumnType('age')).toBe('ordinal')
  })

  it('restoreDataset() returns false and clears when expired', () => {
    const store = useDatasetStore()
    store.load(mockPreview)

    vi.spyOn(Date, 'now').mockReturnValue(Date.now() + 31 * 60 * 1000)

    setActivePinia(createPinia())
    const freshStore = useDatasetStore()
    const restored = freshStore.restoreDataset()

    expect(restored).toBe(false)
    expect(freshStore.isLoaded).toBe(false)
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })

  it('clearDataset() removes sessionStorage key', () => {
    const store = useDatasetStore()
    store.load(mockPreview)
    expect(sessionStorage.getItem(STORAGE_KEY)).not.toBeNull()

    store.clearDataset()
    expect(store.isLoaded).toBe(false)
    expect(sessionStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
