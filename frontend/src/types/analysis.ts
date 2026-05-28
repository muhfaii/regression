export type SessionMode = 'guide' | 'browse'

export interface VariableSlot {
  key: string
  label: string
  required_type: 'continuous' | 'categorical' | 'any'
  multiple: boolean
}

export interface TestDefinition {
  key: string
  name: string
  category: string
  descriptor: string   // ≤5 words
  tooltip: string      // one sentence
  slots: VariableSlot[]
  coming_soon?: boolean
}

export interface AnalysisConfig {
  [slotKey: string]: string | string[]
}

export interface RunRequest {
  session_id: string
  test_key: string
  config: AnalysisConfig
  options: {
    assumption_checks: boolean
    effect_size: boolean
    post_hoc: boolean
    se_type: string
    p_adjust: string
  }
}
