<script setup lang="ts">
defineProps<{ result: Record<string, any> }>()

const SKIP_KEYS = new Set([
  'variables', 'groups', 'coefficients', 'post_hoc',
  'contingency_table', 'outcome_categories',
])
const STATUS_ICON: Record<string, string> = { pass: '✓', amber: '⚠', fail: '✗' }
const STATUS_CLASS: Record<string, string> = { pass: 'check-pass', amber: 'check-amber', fail: 'check-fail' }

function scalarCards(stats: Record<string, unknown>) {
  return Object.entries(stats).filter(
    ([k, v]) => !SKIP_KEYS.has(k) && (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean'),
  )
}

function fmt(val: unknown): string {
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return String(val)
    if (Math.abs(val) < 0.001) return val.toExponential(2)
    if (Math.abs(val) > 999) return val.toFixed(1)
    return val.toFixed(3)
  }
  if (typeof val === 'boolean') return val ? 'Yes' : 'No'
  return String(val)
}

const LABEL_MAP: Record<string, string> = {
  r_squared: 'R²',
  adj_r_squared: 'Adjusted R²',
  f_statistic: 'F-statistic',
  p_value: 'p-value',
  n_obs: 'N',
  chi2_statistic: 'χ²',
  log_likelihood: 'Log-likelihood',
  aic: 'AIC',
  bic: 'BIC',
  rmse: 'RMSE',
  mae: 'MAE',
  dof: 'df',
  n_vars: 'Variables',
  n_factors: 'Factors',
  n_indicators: 'Indicators',
  n_groups: 'Groups',
  n_events: 'Events',
  event_rate: 'Event rate',
  n_subjects: 'Subjects',
  n_predictors: 'Predictors',
  concordance: 'Concordance',
  llf: 'Log-likelihood',
  se_type: 'SE type',
}

function fmtLabel(key: string): string {
  if (LABEL_MAP[key]) return LABEL_MAP[key]
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}
</script>

<template>
  <div class="share-content">
    <div class="share-header">
      <h1 class="result-title">{{ result.test_name }}</h1>
      <p class="result-meta">N = {{ result.n_obs }}</p>
    </div>

    <!-- Scalar stat cards -->
    <div v-if="scalarCards(result.statistics).length" class="stats-cards">
      <div
        v-for="[key, val] in scalarCards(result.statistics)"
        :key="key"
        class="stat-card"
      >
        <div class="stat-label">{{ fmtLabel(key) }}</div>
        <div class="stat-value">{{ fmt(val) }}</div>
      </div>
    </div>

    <!-- Effect size -->
    <div v-if="result.effect_size" class="effect-size-section">
      <span class="effect-label">{{ result.effect_size.name }}:</span>
      <strong>{{ result.effect_size.value.toFixed(3) }}</strong>
      <span class="effect-interp">({{ result.effect_size.interpretation }})</span>
    </div>

    <!-- Assumption checks -->
    <div v-if="result.assumption_checks?.length" class="assumptions-section">
      <h3 class="section-title">Assumption Checks</h3>
      <div
        v-for="check in result.assumption_checks"
        :key="check.name"
        class="check-item"
        :class="STATUS_CLASS[check.status]"
      >
        <span class="check-icon">{{ STATUS_ICON[check.status] }}</span>
        <div>
          <div class="check-name">{{ check.name }}</div>
          <div class="check-detail">{{ check.detail }}</div>
        </div>
      </div>
    </div>

    <!-- APA 7 interpretation -->
    <div v-if="result.interpretation" class="interpretation-section">
      <h3 class="section-title">Interpretation</h3>
      <p class="apa-text">{{ result.interpretation.apa }}</p>
      <p class="plain-text">{{ result.interpretation.plain }}</p>
    </div>
  </div>
</template>

<style scoped>
.share-content { display: flex; flex-direction: column; gap: 28px; }
.share-header { display: flex; flex-direction: column; gap: 4px; }
.result-title { font-size: 24px; margin: 0; }
.result-meta { font-size: 13px; color: var(--color-text-muted); margin: 0; }
.stats-cards { display: flex; flex-wrap: wrap; gap: 12px; }
.stat-card {
  border: 1px solid var(--color-border);
  border-radius: 10px;
  padding: 14px 18px;
  min-width: 120px;
  background: var(--color-surface);
}
.stat-label {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
  margin-bottom: 4px;
}
.stat-value { font-size: 18px; font-weight: 700; }
.effect-size-section { font-size: 14px; }
.effect-label { color: var(--color-text-muted); margin-right: 6px; }
.effect-interp { color: var(--color-text-muted); font-size: 13px; margin-left: 4px; }
.assumptions-section { display: flex; flex-direction: column; gap: 8px; }
.section-title { font-size: 15px; font-weight: 600; margin: 0 0 8px; }
.check-item {
  display: flex;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  border: 1px solid transparent;
}
.check-pass { background: var(--color-green-bg); border-color: var(--color-green-border); }
.check-amber { background: var(--color-amber-bg); border-color: var(--color-amber-border); }
.check-fail { background: var(--color-red-bg); border-color: var(--color-red-border); }
.check-icon { font-weight: 700; font-size: 14px; flex-shrink: 0; }
.check-pass .check-icon { color: var(--color-green); }
.check-amber .check-icon { color: var(--color-amber); }
.check-fail .check-icon { color: var(--color-red); }
.check-name { font-weight: 600; }
.check-detail { color: var(--color-text-muted); margin-top: 2px; }
.interpretation-section { display: flex; flex-direction: column; gap: 12px; }
.apa-text { font-style: italic; font-size: 14px; line-height: 1.6; margin: 0; }
.plain-text { font-size: 14px; line-height: 1.6; color: var(--color-text-muted); margin: 0; }
</style>
