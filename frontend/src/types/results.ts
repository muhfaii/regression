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

export interface DescStat {
  variable: string
  mean: number
  std: number
  min: number
  median: number
  max: number
  missing: number
}

export interface VifEntry {
  variable: string
  vif: number
  verdict: string
}

export interface Remedy {
  priority: number
  kind: string
  description: string
  why: string
}

export interface PerTestRemediation {
  test_id: string
  test_name: string
  verdict: string
  remedies: Remedy[]
  honest_caveat: string
}

export interface CrossPattern {
  id: string
  severity: string
  interpretation: string
  recommendation: string
  triggered_by: string[]
}

export interface Remediation {
  patterns: CrossPattern[]
  per_test: PerTestRemediation[]
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

export interface CoefficientRow {
  coef: number
  se: number
  t: number
  p: number
  ci_low: number
  ci_high: number
  significant: boolean
  p_adjusted?: number
}
