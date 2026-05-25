export type CheckStatus = 'pass' | 'amber' | 'fail'

export interface AssumptionCheck {
  name: string
  status: CheckStatus
  detail: string
  fix_suggestion: string | null
}

export interface EffectSize {
  name: string
  value: number
  interpretation: string
}

export interface Interpretation {
  plain: string
  apa: string
  technical: string
}

export interface AnalysisResult {
  result_id: string
  test_key: string
  test_name: string
  n_obs: number
  statistics: Record<string, unknown>
  effect_size: EffectSize | null
  assumption_checks: AssumptionCheck[]
  interpretation: Interpretation
  warnings: string[]
}
