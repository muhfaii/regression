export type SessionMode = 'guide' | 'browse'

export type TestType = 'column_assignment' | 'parameter_input'

export interface ParameterField {
  key: string
  label: string
  type: 'number' | 'select' | 'boolean'
  options?: string[]
  default?: number | string | boolean
}

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
  type?: TestType
  parameters?: ParameterField[]
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
    extras?: Record<string, any>
  }
}
