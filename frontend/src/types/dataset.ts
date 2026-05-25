export type ColumnType = 'continuous' | 'categorical' | 'ordinal' | 'date'
export type DatasetContext = 'survey' | 'generic'

export interface ColumnInfo {
  name: string
  raw_dtype: string
  inferred_type: ColumnType
  missing_count: number
  missing_pct: number
  has_masked_numeric: boolean
  // User override (client-side only, not in API response)
  override_type?: ColumnType
}

export interface DatasetPreview {
  session_id: string
  filename: string
  row_count: number
  columns: ColumnInfo[]
  dataset_context: DatasetContext
  warnings: string[]
}
