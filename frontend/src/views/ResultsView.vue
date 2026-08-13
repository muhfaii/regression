<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useResultsStore } from '../stores/results'
import { useSessionStore } from '../stores/session'
import type { DescStat, VifEntry, Remediation, CoefficientRow } from '../types/results'
import ExportPanel from '../components/results/ExportPanel.vue'

import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend } from 'chart.js'
import { Line } from 'vue-chartjs'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

const router = useRouter()
const results = useResultsStore()
const session = useSessionStore()

const result = computed(() => results.activeResult)
const activeTab = ref<'plain' | 'apa' | 'technical'>(
  session.mode === 'browse' ? 'technical' : 'plain'
)

function sparkBar(val: number): string {
  const abs = Math.abs(val)
  if (abs < 0.05) return '·'
  const level = Math.min(Math.floor(abs * 8), 7)
  const bar = '▁▂▃▄▅▆▇█'[level]
  return val >= 0 ? '+' + bar : '−' + bar
}

function corrColor(val: number): string {
  const abs = Math.abs(val)
  if (abs < 0.1) return 'transparent'
  const sat = Math.min(abs * 1.2, 1)
  if (val > 0) return `rgba(59, 130, 246, ${sat * 0.35})`
  return `rgba(239, 68, 68, ${sat * 0.35})`
}

const STATUS_ICON: Record<string, string> = { pass: '✓', amber: '⚠', fail: '✗' }
const STATUS_CLASS: Record<string, string> = { pass: 'check-pass', amber: 'check-amber', fail: 'check-fail' }

// Top-level scalar keys rendered as headline cards (skip structural sub-objects)
const SKIP_KEYS = new Set(['variables', 'groups', 'coefficients', 'post_hoc', 'post_hoc_bonferroni', 'contingency_table', 'outcome_categories', 'variable_names', 'matrix_pearson', 'matrix_spearman', 'matrix_kendall', 'matrix_p_pearson', 'matrix_p_spearman', 'matrix_p_kendall', 'matrix_p_pearson_adj', 'matrix_p_spearman_adj', 'matrix_p_kendall_adj', 'p_adjust_method', 'n_vars', 'terms', 'bplm', 'hausman', 'selection_steps', 'absorbed_vars', 'entity_col', 'time_col', 'model_type', 'simple_slopes', 'jn_region', 'floodlight', 'interaction_f2', 'predictor', 'moderator', 'covariates', 'path_a', 'path_b', 'path_c', 'path_c_prime', 'indirect_effect', 'sobel_z', 'sobel_p', 'bootstrap_ci_low', 'bootstrap_ci_high', 'proportion_mediated', 'mediation_type', 'r_squared_x_m', 'r_squared_x_y', 'r_squared_xm_y', 'coefficients_x_m', 'coefficients_x_y', 'coefficients_xm_y', 'mediator', 'desc_stats', 'vif_table', 'remediation', 'se_justification', 'se_citation',
  'acf_values', 'pacf_values', 'decomposition', 'forecast_values', 'forecast_ci_low', 'forecast_ci_high', 'arima_residuals', 'adf_critical_values', 'kpss_critical_values', 'arima_order',
  'km_survival_curve', 'cox', 'cox_converged', 'cox_warnings', 'group_names', 'n_events', 'event_rate', 'km_median', 'logrank_statistic', 'logrank_p'])

function scalarCards(stats: Record<string, unknown>) {
  return Object.entries(stats).filter(([k, v]) =>
    !SKIP_KEYS.has(k) && (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean')
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

// Descriptive stats: statistics.variables
const descriptiveVars = computed(() => {
  if (result.value?.test_key !== 'descriptive') return null
  return result.value.statistics.variables as Record<string, Record<string, number>>
})

// Reliability: item-total statistics
const reliabilityItems = computed(() => {
  const r = result.value
  if (r?.test_key !== 'reliability') return null
  const items = r.statistics?.item_statistics as { item: string; corrected_item_total_corr: number; alpha_if_deleted: number | null }[] | undefined
  if (!items || !items.length) return null
  return items
})

// Group summaries: statistics.groups (ANOVA, Mann-Whitney, Kruskal-Wallis)
const groupStats = computed(() => {
  const g = result.value?.statistics?.groups
  if (!g || typeof g !== 'object') return null
  return g as Record<string, Record<string, number>>
})

// Coefficient table: statistics.coefficients (OLS via regression module, Logistic)
const coefficients = computed(() => {
  const c = result.value?.statistics?.coefficients
  if (!c || typeof c !== 'object' || Object.keys(c).length === 0) return null
  return c as Record<string, CoefficientRow>
})

// Descriptive stats for model variables (regression models)
const descStats = computed(() => {
  const d = result.value?.statistics?.desc_stats
  if (!Array.isArray(d) || d.length === 0) return null
  return d as DescStat[]
})

// VIF per-variable table
const vifTable = computed(() => {
  const v = result.value?.statistics?.vif_table
  if (!Array.isArray(v) || v.length === 0) return null
  return v as VifEntry[]
})

// Remediation data (cross-patterns + per-test remedies)
const remediationData = computed(() => {
  const r = result.value?.statistics?.remediation
  if (!r || typeof r !== 'object') return null
  return r as Remediation
})

// SE justification text
const seJustification = computed(() => {
  return result.value?.statistics?.se_justification as string | undefined
})

// SE citation text
const seCitation = computed(() => {
  return result.value?.statistics?.se_citation as string | undefined
})

// Correlation matrix
const corrMatrix = computed(() => {
  const r = result.value
  if (r?.test_key !== 'correlation') return null
  const names = r.statistics?.variable_names as string[] | undefined
  const pearson = r.statistics?.matrix_pearson as number[][] | undefined
  const spearman = r.statistics?.matrix_spearman as number[][] | undefined
  const kendall = r.statistics?.matrix_kendall as number[][] | undefined
  if (!names || !pearson) return null
  return { names, pearson, spearman, kendall }
})

const corrType = ref<'pearson' | 'spearman' | 'kendall'>('pearson')

// Post-hoc: statistics.post_hoc (Tukey)
const postHoc = computed(() => {
  const ph = result.value?.statistics?.post_hoc
  if (!Array.isArray(ph) || ph.length === 0) return null
  return ph as { group1: string; group2: string; mean_diff: number; p_adj: number; reject: boolean }[]
})

// Post-hoc Bonferroni: statistics.post_hoc_bonferroni
const postHocBf = computed(() => {
  const ph = result.value?.statistics?.post_hoc_bonferroni
  if (Array.isArray(ph)) {
    return ph.length > 0 ? { _: ph as { group1: string; group2: string; mean_diff: number; p_adj: number; reject: boolean }[] } : null
  }
  if (ph && typeof ph === 'object') {
    const map = ph as Record<string, { group1: string; group2: string; mean_diff: number; p_adj: number; reject: boolean }[]>
    const entries = Object.entries(map).filter(([, v]) => v.length > 0)
    return entries.length > 0 ? map : null
  }
  return null
})

// Factorial ANOVA terms
const factorialTerms = computed(() => {
  const t = result.value?.statistics?.terms
  if (!Array.isArray(t) || t.length === 0 || result.value?.test_key !== 'factorial_anova') return null
  return t as { term: string; f_statistic: number; p_value: number; df: number; eta_sq: number }[]
})

// Panel regression data
const panelData = computed(() => {
  const r = result.value
  if (r?.test_key !== 'panel_regression') return null
  const s = r.statistics
  return {
    modelType: s.model_type as string,
    bplm: s.bplm as { statistic: number; p_value: number; verdict: string } | null,
    hausman: s.hausman as { statistic: number; p_value: number; verdict: string; dof: number } | null,
    selectionSteps: s.selection_steps as { test_name: string; statistic: number | null; p_value: number | null; verdict: string; chosen_model: string; note: string }[],
    absorbedVars: s.absorbed_vars as string[],
  }
})

// Moderation data
const moderationData = computed(() => {
  const r = result.value
  if (r?.test_key !== 'moderation') return null
  const s = r.statistics
  return {
    simpleSlopes: s.simple_slopes as Record<string, { moderator_value: number; slope: number; se: number; t: number; p: number; ci_low: number; ci_high: number }>,
    jnRegion: s.jn_region as { has_region: boolean; lower_bound: number | null; upper_bound: number | null },
    predictor: s.predictor as string,
    moderator: s.moderator as string,
    outcome: s.outcome as string,
  }
})

// Mediation data
const mediationData = computed(() => {
  const r = result.value
  if (r?.test_key !== 'mediation') return null
  const s = r.statistics
  return {
    pathA: s.path_a as { coef: number; se: number; t: number; p: number },
    pathB: s.path_b as { coef: number; se: number; t: number; p: number },
    pathC: s.path_c as { coef: number; se: number; t: number; p: number },
    pathCPrime: s.path_c_prime as { coef: number; se: number; t: number; p: number },
    indirectEffect: s.indirect_effect as number,
    sobelZ: s.sobel_z as number,
    sobelP: s.sobel_p as number,
    bootstrapCILow: s.bootstrap_ci_low as number,
    bootstrapCIHigh: s.bootstrap_ci_high as number,
    proportionMediated: s.proportion_mediated as number,
    mediationType: s.mediation_type as string,
    predictor: s.predictor as string,
    mediator: s.mediator as string,
    outcome: s.outcome as string,
  }
})

// Time-series data
const timeseriesData = computed(() => {
  const r = result.value
  if (r?.test_key !== 'timeseries') return null
  const s = r.statistics
  return {
    adfPvalue: s.adf_pvalue as number | undefined,
    adfStatistic: s.adf_statistic as number | undefined,
    kpssPvalue: s.kpss_pvalue as number | undefined,
    kpssStatistic: s.kpss_statistic as number | undefined,
    isStationary: s.is_stationary as boolean | undefined,
    ljungBoxStat: s.ljung_box_statistic as number | undefined,
    ljungBoxPval: s.ljung_box_pvalue as number | undefined,
    acfValues: s.acf_values as { lag: number; value: number }[] | undefined,
    pacfValues: s.pacf_values as { lag: number; value: number }[] | undefined,
    isSeasonal: s.is_seasonal as boolean | undefined,
    seasonalPeriod: s.seasonal_period as number | undefined,
    seasonalStrength: s.seasonal_strength as number | undefined,
    arimaOrder: s.arima_order as number[] | undefined,
    arimaAic: s.arima_aic as number | undefined,
    arimaBic: s.arima_bic as number | undefined,
    forecastSteps: s.forecast_steps as number | undefined,
    forecastValues: s.forecast_values as number[] | undefined,
    forecastCiLow: s.forecast_ci_low as number[] | undefined,
    forecastCiHigh: s.forecast_ci_high as number[] | undefined,
  }
})

// Survival data
const survivalData = computed(() => {
  const r = result.value
  if (r?.test_key !== 'survival_analysis') return null
  const s = r.statistics
  return {
    nEvents: s.n_events as number,
    eventRate: s.event_rate as number,
    kmMedian: s.km_median as number | null,
    kmCurve: s.km_survival_curve as { times: number[]; survival: number[]; ci_lower: number[] | null; ci_upper: number[] | null } | undefined,
    logrankStat: s.logrank_statistic as number | undefined,
    logrankP: s.logrank_p as number | undefined,
    groupNames: s.group_names as string[] | undefined,
    cox: s.cox as { n_predictors: number; hr_table: { predictor: string; coef: number; hr: number; se: number; z: number; p: number; ci_lower: number; ci_upper: number }[]; concordance: number; log_likelihood: number } | undefined,
    coxConverged: s.cox_converged as boolean | undefined,
    coxWarnings: s.cox_warnings as string[] | undefined,
  }
})

// Mixed ANOVA data
const mixedAnovaData = computed(() => {
  const r = result.value
  if (r?.test_key !== 'mixed_anova') return null
  const s = r.statistics
  return {
    effects: s.effects as { effect: string; f_statistic: number; df_num: number; df_den: number; p_value: number }[],
    nSubjects: s.n_subjects as number,
    cellStats: s.cell_stats as { [key: string]: string | number }[],
    withinLevels: s.within_levels as string[],
    hasBetween: s.has_between as boolean,
    betweenFactor: s.between_factor as string | undefined,
    mauchly: s.mauchly as { W: number; chi2: number; df: number; p_value: number; eps_gg: number } | undefined,
    postHocWithin: s.post_hoc_within as { level1: string; level2: string; mean_diff: number; t_stat: number; p_adj: number; reject: boolean }[] | undefined,
    postHocBetween: s.post_hoc_between as { group1: string; group2: string; mean_diff: number; p_adj: number; reject: boolean }[] | undefined,
  }
})

// CFA data
const cfaData = computed(() => {
  const r = result.value
  if (r?.test_key !== 'cfa') return null
  const s = r.statistics
  return {
    nIndicators: s.n_indicators as number,
    nFactors: s.n_factors as number,
    chi2: s.chi2 as number,
    df: s.df as number,
    pValue: s.p_value as number,
    cfi: s.cfi as number,
    tli: s.tli as number,
    rmsea: s.rmsea as number,
    rmseaLower: s.rmsea_ci_lower as number,
    rmseaUpper: s.rmsea_ci_upper as number,
    srmr: s.srmr as number,
    converged: s.converged as boolean,
    loadings: s.loadings as { indicator: string; factor: string; loading: number; loading_std: number }[],
    factorCorrelations: s.factor_correlations as { factor1: string; factor2: string; correlation: number }[] | null,
  }
})

const MODEL_TYPE_LABEL: Record<string, string> = {
  fe: 'Fixed Effects', re: 'Random Effects', pooled_ols: 'Pooled OLS',
}
const MODEL_TYPE_COLOR: Record<string, string> = {
  fe: '#7c3aed', re: '#2563eb', pooled_ols: '#6b7280',
}

const chartReady = ref(true)

const kmChartData = computed(() => {
  const d = survivalData.value?.kmCurve
  if (!d) return { labels: [], datasets: [] }
  const baseColor = 'rgba(37, 99, 235, 0.8)'
  const datasets: {
    label: string; data: number[]; stepped: 'before'; borderColor: string;
    backgroundColor: string; borderWidth: number; pointRadius: number;
    borderDash?: number[]; fill?: string | boolean;
  }[] = [
    {
      label: 'Survival probability',
      data: d.survival,
      stepped: 'before' as const,
      borderColor: baseColor,
      backgroundColor: 'transparent',
      borderWidth: 2,
      pointRadius: 0,
    },
  ]
  if (d.ci_lower != null && d.ci_upper != null) {
    datasets.push({
      label: '95% CI (upper)',
      data: d.ci_upper,
      stepped: 'before' as const,
      borderColor: 'rgba(37, 99, 235, 0.25)',
      backgroundColor: 'rgba(37, 99, 235, 0.08)',
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
      fill: '+2',
    })
    datasets.push({
      label: '95% CI (lower)',
      data: d.ci_lower,
      stepped: 'before' as const,
      borderColor: 'rgba(37, 99, 235, 0.25)',
      backgroundColor: 'transparent',
      borderWidth: 1,
      borderDash: [4, 4],
      pointRadius: 0,
      fill: false,
    })
  }
  return { labels: d.times as (string | number)[], datasets }
})

const kmChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  scales: {
    x: {
      title: { display: true, text: 'Time' },
    },
    y: {
      title: { display: true, text: 'Survival probability' },
      min: 0,
      max: 1,
    },
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx: { raw: unknown }) => `S(t) = ${Number(ctx.raw).toFixed(3)}`,
      },
    },
  },
}

function newAnalysis() {
  router.push(session.mode === 'guide' ? '/guide' : '/browse')
}
</script>

<template>
  <div class="results-view">
    <!-- Left sidebar -->
    <aside class="results-sidebar">
      <button class="new-analysis-btn" @click="newAnalysis">+ New analysis</button>
      <div class="history-label">Recent analyses</div>
      <div
        v-for="r in results.history"
        :key="r.result_id"
        class="history-item"
        :class="{ active: r.result_id === results.activeResultId }"
        @click="results.setActive(r.result_id)"
      >
        {{ r.test_name }}
      </div>
      <p class="signin-nudge">Create an account to save your analysis history.</p>
    </aside>

    <!-- Main results -->
    <div v-if="result" class="results-main" aria-live="polite" aria-atomic="false">
      <h1 class="result-title">{{ result.test_name }}</h1>
      <p class="result-meta">N = {{ result.n_obs }}</p>

      <!-- Interpretation tabs (plain-language summary first, technical detail below) -->
      <div class="interpretation-section">
        <h3 class="section-title">Interpretation</h3>
        <div class="tabs" role="tablist">
          <button
            v-for="[key, label] in ([['plain', 'Plain English'], ['apa', 'APA 7'], ['technical', 'Technical']] as [string, string][])"
            :key="key"
            class="tab-btn"
            :class="{ active: activeTab === key }"
            role="tab"
            :aria-selected="activeTab === key"
            @click="activeTab = key as 'plain' | 'apa' | 'technical'"
          >
            {{ label }}
          </button>
        </div>
        <div class="tab-content">
          <p v-if="activeTab === 'plain'">{{ result.interpretation.plain }}</p>
          <p v-if="activeTab === 'apa'" class="apa-text">{{ result.interpretation.apa }}</p>
          <p v-if="activeTab === 'technical'" class="mono-text">{{ result.interpretation.technical }}</p>
        </div>
      </div>

      <!-- Headline stat cards (scalars only) -->
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

      <!-- Descriptive: per-variable table -->
      <div v-if="descriptiveVars" class="section">
        <h3 class="section-title">Summary statistics</h3>
        <div v-for="(stats, varName) in descriptiveVars" :key="varName" class="var-block">
          <div class="var-name">{{ varName }}</div>
          <div class="desc-grid">
            <div v-for="(val, stat) in stats" :key="stat" class="desc-cell">
              <div class="desc-label">{{ fmtLabel(String(stat)) }}</div>
              <div class="desc-val">{{ fmt(val) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Reliability: item-total statistics -->
      <div v-if="reliabilityItems" class="section">
        <h3 class="section-title">Item-total statistics</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Item</th>
              <th>Corrected item-total correlation</th>
              <th>Alpha if deleted</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in reliabilityItems" :key="item.item">
              <td class="group-name">{{ item.item }}</td>
              <td>{{ item.corrected_item_total_corr.toFixed(4) }}</td>
              <td>{{ item.alpha_if_deleted != null ? item.alpha_if_deleted.toFixed(4) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Group summary table (ANOVA, Mann-Whitney, Kruskal-Wallis) -->
      <div v-if="groupStats" class="section">
        <h3 class="section-title">Group summary</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Group</th>
              <th v-for="col in Object.keys(Object.values(groupStats)[0])" :key="col">{{ fmtLabel(col) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(stats, group) in groupStats" :key="group">
              <td class="group-name">{{ group }}</td>
              <td v-for="val in Object.values(stats)" :key="String(val)">{{ fmt(val) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Coefficient table -->
      <div v-if="coefficients" class="section">
        <h3 class="section-title">Coefficients</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Predictor</th>
              <th>Coefficient</th>
              <th>SE</th>
              <th>t</th>
              <th>p</th>
              <th>95% CI</th>
              <th>Sig.</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, pred) in coefficients" :key="pred" :class="{ 'sig-row': row.significant }">
              <td class="group-name">{{ pred }}</td>
              <td>{{ row.coef }}</td>
              <td>{{ row.se }}</td>
              <td>{{ row.t }}</td>
              <td>{{ row.p.toFixed(4) }}</td>
              <td>[{{ row.ci_low }}, {{ row.ci_high }}]</td>
              <td>
                <span v-if="row.significant" class="badge-sig" style="font-size:12px;font-weight:700;color:var(--color-accent);background:var(--color-accent-tint);padding:2px 8px;border-radius:10px;">p &lt; 0.05</span>
                <span v-else class="badge-ns" style="font-size:12px;color:var(--color-text-muted);background:var(--surface-2);padding:2px 8px;border-radius:10px;">n.s.</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="seCitation" style="margin-top:8px;font-size:13px;color:var(--color-text-secondary);">{{ seCitation }}</p>
        <p v-if="seJustification" style="margin-top:4px;font-size:12px;color:var(--color-text-muted);font-style:italic;">{{ seJustification }}</p>
      </div>

      <!-- Descriptive stats for regression model variables -->
      <div v-if="descStats && result?.test_key !== 'descriptive'" class="section">
        <h3 class="section-title">Descriptive statistics</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Variable</th>
              <th>Mean</th>
              <th>Std Dev</th>
              <th>Min</th>
              <th>Median</th>
              <th>Max</th>
              <th>Missing</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in descStats" :key="s.variable">
              <td class="group-name">{{ s.variable }}</td>
              <td>{{ s.mean }}</td>
              <td>{{ s.std }}</td>
              <td>{{ s.min }}</td>
              <td>{{ s.median }}</td>
              <td>{{ s.max }}</td>
              <td>{{ s.missing }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- VIF per-variable table -->
      <div v-if="vifTable" class="section">
        <h3 class="section-title">Variance Inflation Factor (VIF)</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Variable</th>
              <th>VIF</th>
              <th>Flag</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="e in vifTable" :key="e.variable">
              <td class="group-name">{{ e.variable }}</td>
              <td>{{ e.vif }}</td>
              <td>
                <span v-if="e.verdict === 'concern'" class="vif-badge vif-concern">Concern (&gt;10)</span>
                <span v-else-if="e.verdict === 'examine'" class="vif-badge vif-examine">Examine (5–10)</span>
                <span v-else class="vif-badge vif-ok">OK</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Model robustness / SE justification -->
      <div v-if="seJustification" class="section">
        <h3 class="section-title">Model robustness</h3>
        <div class="robustness-card">
          <div class="robustness-row">
            <span class="robustness-label">Standard error type</span>
            <span class="robustness-value">{{ result?.statistics?.se_type || 'classical' }}</span>
          </div>
          <div class="robustness-row">
            <span class="robustness-label">Justification</span>
            <span class="robustness-value">{{ seJustification }}</span>
          </div>
          <p v-if="seCitation" class="robustness-citation">{{ seCitation }}</p>
        </div>
      </div>

      <!-- Remediation / Recommendations -->
      <div v-if="remediationData" class="section">
        <h3 class="section-title">Recommendations</h3>

        <!-- Cross-diagnostic patterns -->
        <div v-if="remediationData.patterns.length" class="remediation-patterns">
          <div
            v-for="p in remediationData.patterns"
            :key="p.id"
            class="pattern-card"
            :class="'pattern-' + p.severity"
          >
            <div class="pattern-title">{{ p.id.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) }}</div>
            <p class="pattern-interp">{{ p.interpretation }}</p>
            <p class="pattern-rec"><strong>Recommendation:</strong> {{ p.recommendation }}</p>
          </div>
        </div>

        <!-- Per-test remedies -->
        <div v-for="t in remediationData.per_test" :key="t.test_id" class="remedy-group">
          <p class="remedy-group-title">
            <span class="remedy-verdict-badge" :class="'verdict-' + t.verdict">{{ t.verdict.toUpperCase() }}</span>
            {{ t.test_name }}
          </p>
          <div v-for="rem in t.remedies" :key="rem.priority" class="remedy-card">
            <div class="remedy-header">
              <span class="remedy-num">{{ rem.priority }}.</span>
              <span class="remedy-desc">{{ rem.description }}</span>
              <span class="remedy-kind" :class="'kind-' + rem.kind">{{ rem.kind === 'quick_fix' ? 'quick fix' : 'thinking fix' }}</span>
            </div>
            <p class="remedy-why">{{ rem.why }}</p>
          </div>
          <p v-if="t.honest_caveat" class="remedy-caveat">{{ t.honest_caveat }}</p>
        </div>
      </div>

      <!-- Correlation matrix -->
      <div v-if="corrMatrix" class="section">
        <h3 class="section-title">Correlation matrix</h3>
        <div v-if="result.statistics.p_adjust_method" class="adjustment-badge">
          P-values adjusted using <strong>{{ fmtLabel(result.statistics.p_adjust_method as string) }}</strong>
        </div>
        <div class="tabs">
          <button
            v-for="ct in (['pearson', 'spearman', 'kendall'] as const)"
            :key="ct"
            class="tab-btn"
            :class="{ active: corrType === ct }"
            @click="corrType = ct"
          >
            {{ ct.charAt(0).toUpperCase() + ct.slice(1) }}
          </button>
        </div>
        <div class="corr-matrix-wrapper">
          <table class="corr-matrix">
            <thead>
              <tr>
                <th></th>
                <th v-for="n in corrMatrix.names" :key="n" class="corr-col-header">{{ n }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in corrMatrix[corrType]" :key="i">
                <th class="corr-row-header">{{ corrMatrix.names[i] }}</th>
                <td
                  v-for="(val, j) in row"
                  :key="j"
                  class="corr-cell"
                  :style="{ background: corrColor(val) }"
                  :class="{ 'corr-diag': i === j }"
                >
                  {{ val.toFixed(2) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Factorial ANOVA: terms table -->
      <div v-if="factorialTerms" class="section">
        <h3 class="section-title">ANOVA summary</h3>
        <table class="data-table">
          <thead>
            <tr><th>Term</th><th>F</th><th>df</th><th>p</th><th>η²</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in factorialTerms" :key="t.term" :class="{ 'sig-row': t.p_value < 0.05 }">
              <td class="group-name">{{ t.term }}</td>
              <td>{{ t.f_statistic.toFixed(3) }}</td>
              <td>{{ t.df }}</td>
              <td>{{ t.p_value.toFixed(4) }}</td>
              <td>{{ t.eta_sq.toFixed(4) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Post-hoc table (Tukey) -->
      <div v-if="postHoc" class="section">
        <h3 class="section-title">Post-hoc comparisons (Tukey HSD)</h3>
        <table class="data-table">
          <thead>
            <tr><th>Group 1</th><th>Group 2</th><th>Mean diff</th><th>p (adj)</th><th>Significant</th></tr>
          </thead>
          <tbody>
            <tr v-for="row in postHoc" :key="row.group1 + row.group2" :class="{ 'sig-row': row.reject }">
              <td>{{ row.group1 }}</td>
              <td>{{ row.group2 }}</td>
              <td>{{ row.mean_diff.toFixed(4) }}</td>
              <td>{{ row.p_adj.toFixed(4) }}</td>
              <td>{{ row.reject ? '✓' : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Post-hoc table (Bonferroni) -->
      <div v-if="postHocBf" class="section">
        <h3 class="section-title">
          Post-hoc comparisons (Bonferroni)
          <span v-if="factorialTerms" class="subtitle">per factor</span>
        </h3>
        <template v-for="(rows, factor) in postHocBf" :key="factor">
          <h4 v-if="factor !== '_'" class="factor-heading">{{ factor }}</h4>
          <table class="data-table" :class="{ 'bf-table': factor !== '_' }">
            <thead>
              <tr><th>Group 1</th><th>Group 2</th><th>Mean diff</th><th>p (adj)</th><th>Significant</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.group1 + row.group2" :class="{ 'sig-row': row.reject }">
                <td>{{ row.group1 }}</td>
                <td>{{ row.group2 }}</td>
                <td>{{ row.mean_diff.toFixed(4) }}</td>
                <td>{{ row.p_adj.toFixed(4) }}</td>
                <td>{{ row.reject ? '✓' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </div>

      <!-- Panel regression: model badge + test cards -->
      <div v-if="panelData" class="section">
        <div class="panel-model-badge" :style="{ background: MODEL_TYPE_COLOR[panelData.modelType] || '#6b7280' }">
          {{ MODEL_TYPE_LABEL[panelData.modelType] || panelData.modelType }}
        </div>
      </div>

      <div v-if="panelData?.bplm" class="section">
        <h3 class="section-title">Breusch-Pagan LM test</h3>
        <div class="panel-test-card">
          <div class="panel-test-row"><span class="panel-test-label">Statistic</span><span>{{ panelData.bplm.statistic }}</span></div>
          <div class="panel-test-row"><span class="panel-test-label">p-value</span><span>{{ panelData.bplm.p_value }}</span></div>
          <div class="panel-test-row"><span class="panel-test-label">Verdict</span><span>{{ panelData.bplm.verdict }}</span></div>
        </div>
      </div>

      <div v-if="panelData?.hausman" class="section">
        <h3 class="section-title">Hausman test</h3>
        <div class="panel-test-card">
          <div class="panel-test-row"><span class="panel-test-label">Statistic</span><span>{{ panelData.hausman.statistic }}</span></div>
          <div class="panel-test-row"><span class="panel-test-label">p-value</span><span>{{ panelData.hausman.p_value }}</span></div>
          <div class="panel-test-row"><span class="panel-test-label">df</span><span>{{ panelData.hausman.dof }}</span></div>
          <div class="panel-test-row"><span class="panel-test-label">Verdict</span><span>{{ panelData.hausman.verdict }}</span></div>
        </div>
      </div>

      <div v-if="panelData?.selectionSteps?.length" class="section">
        <h3 class="section-title">Model selection</h3>
        <ol class="panel-timeline">
          <li v-for="(step, i) in panelData.selectionSteps" :key="i" class="panel-timeline-step">
            <div class="panel-step-header">
              <span class="panel-step-name">{{ step.test_name }}</span>
              <span class="panel-step-verdict">{{ step.verdict }}</span>
            </div>
            <div v-if="step.statistic != null" class="panel-step-detail">
              χ²({{ step.note === 'BP-LM test' ? '?' : step.note }}) = {{ step.statistic }}, p = {{ step.p_value }}
            </div>
            <div class="panel-step-outcome">
              <span class="model-pill" :class="'model-' + step.chosen_model">
                {{ {fe: 'FE', re: 'RE', pooled_ols: 'Pooled'}[step.chosen_model] || step.chosen_model }}
              </span>
              chosen
            </div>
          </li>
        </ol>
      </div>

      <div v-if="panelData?.absorbedVars?.length" class="section">
        <h3 class="section-title">Absorbed variables</h3>
        <p class="panel-absorbed-note">
          {{ panelData.absorbedVars.join(', ') }} — dropped due to time-invariance in FE estimation.
        </p>
      </div>

      <!-- Moderation: simple slopes table -->
      <div v-if="moderationData" class="section">
        <h3 class="section-title">Simple slopes</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Moderator level</th>
              <th>Value</th>
              <th>Slope</th>
              <th>SE</th>
              <th>t</th>
              <th>p</th>
              <th>95% CI</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, level) in moderationData.simpleSlopes" :key="level" :class="{ 'sig-row': row.p < 0.05 }">
              <td class="group-name">{{ fmtLabel(level) }}</td>
              <td>{{ row.moderator_value }}</td>
              <td>{{ row.slope }}</td>
              <td>{{ row.se }}</td>
              <td>{{ row.t }}</td>
              <td>{{ row.p.toFixed(4) }}</td>
              <td>[{{ row.ci_low }}, {{ row.ci_high }}]</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Moderation: Johnson-Neyman region -->
      <div v-if="moderationData?.jnRegion?.has_region" class="section">
        <h3 class="section-title">Johnson-Neyman significance region</h3>
        <p class="jn-text">
          The simple slope of {{ moderationData.predictor }} on {{ moderationData.outcome }}
          is significant
          <template v-if="moderationData.jnRegion.lower_bound !== null && moderationData.jnRegion.upper_bound !== null">
            when {{ moderationData.moderator }} is between {{ moderationData.jnRegion.lower_bound }} and {{ moderationData.jnRegion.upper_bound }}.
          </template>
          <template v-else-if="moderationData.jnRegion.lower_bound !== null">
            when {{ moderationData.moderator }} is above {{ moderationData.jnRegion.lower_bound }}.
          </template>
          <template v-else-if="moderationData.jnRegion.upper_bound !== null">
            when {{ moderationData.moderator }} is below {{ moderationData.jnRegion.upper_bound }}.
          </template>
        </p>
      </div>

      <!-- Mediation: path coefficients table -->
      <div v-if="mediationData" class="section">
        <h3 class="section-title">Mediation paths</h3>
        <table class="data-table">
          <thead>
            <tr>
              <th>Path</th>
              <th>Description</th>
              <th>Coefficient</th>
              <th>SE</th>
              <th>t</th>
              <th>p</th>
            </tr>
          </thead>
          <tbody>
            <tr :class="{ 'sig-row': mediationData.pathA.p < 0.05 }">
              <td class="group-name">a</td>
              <td>{{ mediationData.predictor }} → {{ mediationData.mediator }}</td>
              <td>{{ mediationData.pathA.coef }}</td>
              <td>{{ mediationData.pathA.se }}</td>
              <td>{{ mediationData.pathA.t }}</td>
              <td>{{ mediationData.pathA.p.toFixed(4) }}</td>
            </tr>
            <tr :class="{ 'sig-row': mediationData.pathB.p < 0.05 }">
              <td class="group-name">b</td>
              <td>{{ mediationData.mediator }} → {{ mediationData.outcome }}</td>
              <td>{{ mediationData.pathB.coef }}</td>
              <td>{{ mediationData.pathB.se }}</td>
              <td>{{ mediationData.pathB.t }}</td>
              <td>{{ mediationData.pathB.p.toFixed(4) }}</td>
            </tr>
            <tr :class="{ 'sig-row': mediationData.pathC.p < 0.05 }">
              <td class="group-name">c (total)</td>
              <td>{{ mediationData.predictor }} → {{ mediationData.outcome }}</td>
              <td>{{ mediationData.pathC.coef }}</td>
              <td>{{ mediationData.pathC.se }}</td>
              <td>{{ mediationData.pathC.t }}</td>
              <td>{{ mediationData.pathC.p.toFixed(4) }}</td>
            </tr>
            <tr :class="{ 'sig-row': mediationData.pathCPrime.p < 0.05 }">
              <td class="group-name">c' (direct)</td>
              <td>{{ mediationData.predictor }} → {{ mediationData.outcome }} (controlling for {{ mediationData.mediator }})</td>
              <td>{{ mediationData.pathCPrime.coef }}</td>
              <td>{{ mediationData.pathCPrime.se }}</td>
              <td>{{ mediationData.pathCPrime.t }}</td>
              <td>{{ mediationData.pathCPrime.p.toFixed(4) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Mediation: indirect effect with Sobel test and bootstrap CI -->
      <div v-if="mediationData" class="section">
        <h3 class="section-title">Indirect effect</h3>
        <div class="panel-test-card">
          <div class="panel-test-row">
            <span class="panel-test-label">Indirect effect (a × b)</span>
            <span>{{ mediationData.indirectEffect }}</span>
          </div>
          <div class="panel-test-row">
            <span class="panel-test-label">Sobel z</span>
            <span>{{ mediationData.sobelZ }}</span>
          </div>
          <div class="panel-test-row">
            <span class="panel-test-label">Sobel p</span>
            <span>{{ mediationData.sobelP.toFixed(4) }}</span>
          </div>
          <div class="panel-test-row">
            <span class="panel-test-label">Bootstrap 95% CI</span>
            <span>[{{ mediationData.bootstrapCILow }}, {{ mediationData.bootstrapCIHigh }}]</span>
          </div>
          <div class="panel-test-row">
            <span class="panel-test-label">Proportion mediated</span>
            <span>{{ (mediationData.proportionMediated * 100).toFixed(1) }}%</span>
          </div>
          <div class="panel-test-row">
            <span class="panel-test-label">Mediation type</span>
            <span class="mediation-badge" :class="'mediation-' + mediationData.mediationType">{{ mediationData.mediationType }}</span>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════════════════════════════
           Survival analysis
           ═══════════════════════════════════════════════════════════════════ -->
      <!-- Survival overview stats -->
      <div v-if="survivalData" class="section">
        <h3 class="section-title">Survival summary</h3>
        <div class="survival-stats-grid">
          <div class="test-card">
            <div class="test-card-title">Median survival</div>
            <div class="test-card-stat">{{ survivalData.kmMedian != null ? survivalData.kmMedian.toFixed(1) : 'Not reached' }}</div>
          </div>
          <div class="test-card">
            <div class="test-card-title">Events</div>
            <div class="test-card-stat">{{ survivalData.nEvents }} / {{ result.n_obs }} ({{ (survivalData.eventRate * 100).toFixed(1) }}%)</div>
          </div>
          <div v-if="survivalData.logrankP != null" class="test-card" :class="survivalData.logrankP < 0.05 ? 'test-pass' : 'test-amber'">
            <div class="test-card-title">Log-rank test</div>
            <div class="test-card-stat">χ² = {{ survivalData.logrankStat?.toFixed(2) }}</div>
            <div class="test-card-stat">p = {{ survivalData.logrankP.toFixed(4) }}</div>
            <div class="test-card-verdict">{{ survivalData.logrankP < 0.05 ? '✓ Significant' : 'Not significant' }}</div>
          </div>
        </div>
      </div>

      <!-- KM survival curve chart -->
      <div v-if="survivalData?.kmCurve" class="section">
        <h3 class="section-title">Kaplan-Meier survival curve</h3>
        <div class="chart-wrapper">
          <Line
            v-if="chartReady"
            :data="kmChartData"
            :options="kmChartOptions"
          />
        </div>
      </div>

      <!-- Cox PH model table -->
      <div v-if="survivalData?.cox" class="section">
        <h3 class="section-title">Cox proportional hazards model</h3>
        <div v-if="!survivalData.coxConverged" class="warning-banner">
          ⚠ Cox model did not converge. Results may be unreliable.
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Predictor</th>
              <th>Coefficient</th>
              <th>Hazard Ratio</th>
              <th>SE</th>
              <th>z</th>
              <th>p</th>
              <th>95% CI</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in survivalData.cox.hr_table" :key="row.predictor" :class="{ 'sig-row': row.p < 0.05 }">
              <td class="group-name">{{ row.predictor }}</td>
              <td>{{ row.coef != null ? row.coef.toFixed(4) : '—' }}</td>
              <td>{{ row.hr != null ? row.hr.toFixed(4) : '—' }}</td>
              <td>{{ row.se != null ? row.se.toFixed(4) : '—' }}</td>
              <td>{{ row.z != null ? row.z.toFixed(4) : '—' }}</td>
              <td>{{ row.p != null ? row.p.toFixed(4) : '—' }}</td>
              <td>{{ row.ci_lower != null ? `[${row.ci_lower.toFixed(4)}, ${row.ci_upper.toFixed(4)}]` : '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div class="cox-fit-card">
          <span class="cox-fit-label">Concordance:</span>
          <strong>{{ survivalData.cox.concordance.toFixed(4) }}</strong>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════════════════════════════
           Time-series analysis
           ═══════════════════════════════════════════════════════════════════ -->
      <!-- Stationarity tests -->
      <div v-if="timeseriesData" class="section">
        <h3 class="section-title">Stationarity tests</h3>
        <div class="stationarity-grid">
          <div v-if="timeseriesData.adfPvalue != null" class="test-card" :class="timeseriesData.isStationary ? 'test-pass' : 'test-fail'">
            <div class="test-card-title">ADF test</div>
            <div class="test-card-stat">stat = {{ timeseriesData.adfStatistic?.toFixed(4) }}</div>
            <div class="test-card-stat">p = {{ timeseriesData.adfPvalue.toFixed(4) }}</div>
            <div class="test-card-verdict">{{ timeseriesData.isStationary ? '✓ Stationary' : '✗ Non-stationary' }}</div>
          </div>
          <div v-if="timeseriesData.kpssPvalue != null" class="test-card" :class="timeseriesData.kpssPvalue < 0.05 ? 'test-fail' : 'test-pass'">
            <div class="test-card-title">KPSS test</div>
            <div class="test-card-stat">stat = {{ timeseriesData.kpssStatistic?.toFixed(4) }}</div>
            <div class="test-card-stat">p = {{ timeseriesData.kpssPvalue.toFixed(4) }}</div>
            <div class="test-card-verdict">{{ timeseriesData.kpssPvalue < 0.05 ? '✗ Non-stationary' : '✓ Trend-stationary' }}</div>
          </div>
        </div>
        <div v-if="timeseriesData.ljungBoxPval != null" class="ljung-box-card">
          <span class="ljung-box-label">Ljung-Box Q:</span>
          <span>χ² = {{ timeseriesData.ljungBoxStat?.toFixed(4) }}, p = {{ timeseriesData.ljungBoxPval.toFixed(4) }}</span>
        </div>
      </div>

      <!-- ACF/PACF table -->
      <div v-if="timeseriesData?.acfValues?.length" class="section">
        <h3 class="section-title">Autocorrelation function (ACF) &amp; Partial ACF</h3>
        <div class="acf-table-wrapper">
          <table class="acf-table">
            <thead>
              <tr>
                <th>Lag</th>
                <th>ACF</th>
                <th>Spark</th>
                <th>PACF</th>
                <th>Spark</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(acfRow, i) in timeseriesData.acfValues.slice(0, 21)" :key="i">
                <td class="acf-lag">{{ acfRow.lag }}</td>
                <td class="acf-val">{{ acfRow.value.toFixed(4) }}</td>
                <td class="acf-spark"><span class="spark-text">{{ sparkBar(acfRow.value) }}</span></td>
                <td class="acf-val">{{ (timeseriesData.pacfValues?.[i]?.value ?? 0).toFixed(4) }}</td>
                <td class="acf-spark"><span class="spark-text">{{ sparkBar(timeseriesData.pacfValues?.[i]?.value ?? 0) }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Seasonal decomposition -->
      <div v-if="timeseriesData?.isSeasonal" class="section">
        <h3 class="section-title">Seasonal decomposition</h3>
        <div class="seasonal-card">
          <div class="seasonal-row"><span class="seasonal-label">Detected seasonal period</span><span>{{ timeseriesData.seasonalPeriod }}</span></div>
          <div v-if="timeseriesData.seasonalStrength != null" class="seasonal-row">
            <span class="seasonal-label">Seasonal strength</span>
            <span>{{ timeseriesData.seasonalStrength.toFixed(4) }}</span>
          </div>
        </div>
      </div>

      <!-- ARIMA model -->
      <div v-if="timeseriesData?.arimaOrder" class="section">
        <h3 class="section-title">ARIMA model</h3>
        <div class="arima-card">
          <div class="arima-row"><span class="arima-label">Order (p,d,q)</span><span class="arima-value">({{ timeseriesData.arimaOrder.join(', ') }})</span></div>
          <div v-if="timeseriesData.arimaAic != null" class="arima-row"><span class="arima-label">AIC</span><span>{{ timeseriesData.arimaAic.toFixed(2) }}</span></div>
          <div v-if="timeseriesData.arimaBic != null" class="arima-row"><span class="arima-label">BIC</span><span>{{ timeseriesData.arimaBic.toFixed(2) }}</span></div>
        </div>
      </div>

      <!-- Forecast table -->
      <div v-if="timeseriesData?.forecastValues?.length" class="section">
        <h3 class="section-title">Forecast ({{ timeseriesData.forecastSteps }} steps)</h3>
        <div class="forecast-wrapper">
          <table class="forecast-table">
            <thead>
              <tr><th>Step</th><th>Forecast</th><th>95% CI Low</th><th>95% CI High</th><th>Range</th></tr>
            </thead>
            <tbody>
              <tr v-for="(fv, i) in timeseriesData.forecastValues" :key="i">
                <td class="fcast-step">{{ i + 1 }}</td>
                <td class="fcast-val">{{ fv.toFixed(4) }}</td>
                <td class="fcast-ci">{{ (timeseriesData.forecastCiLow?.[i] ?? 0).toFixed(4) }}</td>
                <td class="fcast-ci">{{ (timeseriesData.forecastCiHigh?.[i] ?? 0).toFixed(4) }}</td>
                <td class="fcast-spark">
                  <span class="spark-range">
                    {{ sparkBar((timeseriesData.forecastCiLow?.[i] ?? 0) - fv) }}<span class="spark-dot">●</span>{{ sparkBar((timeseriesData.forecastCiHigh?.[i] ?? 0) - fv) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════════════════════════════
           Mixed ANOVA
           ═══════════════════════════════════════════════════════════════════ -->
      <div v-if="mixedAnovaData" class="section">
        <h3 class="section-title">Mixed ANOVA: {{ result.test_name }}</h3>
        <p class="result-meta">{{ mixedAnovaData.nSubjects }} subjects, {{ result.n_obs }} observations</p>

        <!-- Sphericity test -->
        <div v-if="mixedAnovaData.mauchly" class="section">
          <div class="sphericity-card" :class="mixedAnovaData.mauchly.p_value > 0.05 ? 'test-pass' : 'test-amber'">
            <div class="test-card-title">Mauchly's test of sphericity</div>
            <div class="test-card-stat">W = {{ mixedAnovaData.mauchly.W.toFixed(4) }}, χ²({{ mixedAnovaData.mauchly.df }}) = {{ mixedAnovaData.mauchly.chi2.toFixed(2) }}, p = {{ mixedAnovaData.mauchly.p_value.toFixed(4) }}</div>
            <div v-if="mixedAnovaData.mauchly.p_value < 0.05" class="test-card-stat">Greenhouse-Geisser ε = {{ mixedAnovaData.mauchly.eps_gg.toFixed(4) }}</div>
            <div class="test-card-verdict">{{ mixedAnovaData.mauchly.p_value > 0.05 ? '✓ Sphericity assumed' : 'Sphericity violated' }}</div>
          </div>
        </div>

        <!-- Effects table -->
        <table class="data-table">
          <thead>
            <tr><th>Effect</th><th>F</th><th>df<sub>num</sub></th><th>df<sub>den</sub></th><th>p</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in mixedAnovaData.effects" :key="e.effect" :class="{ 'sig-row': e.p_value < 0.05 }">
              <td class="group-name">{{ e.effect }}</td>
              <td>{{ e.f_statistic.toFixed(3) }}</td>
              <td>{{ e.df_num }}</td>
              <td>{{ e.df_den }}</td>
              <td>{{ e.p_value.toFixed(4) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- Cell descriptive stats -->
        <div v-if="mixedAnovaData.cellStats.length" class="section">
          <h4 class="subsection-title">Descriptive statistics per cell</h4>
          <table class="data-table">
            <thead>
              <tr>
                <th v-for="col in Object.keys(mixedAnovaData.cellStats[0])" :key="col">{{ col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in mixedAnovaData.cellStats" :key="i">
                <td v-for="(val, key) in row" :key="key">{{ val }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Post-hoc within -->
        <div v-if="mixedAnovaData.postHocWithin?.length" class="section">
          <h4 class="subsection-title">Post-hoc comparisons (within-subjects, Bonferroni)</h4>
          <table class="data-table">
            <thead>
              <tr><th>Level 1</th><th>Level 2</th><th>Mean diff</th><th>t</th><th>p (adj)</th><th>Significant</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in mixedAnovaData.postHocWithin" :key="row.level1 + row.level2" :class="{ 'sig-row': row.reject }">
                <td>{{ row.level1 }}</td><td>{{ row.level2 }}</td>
                <td>{{ row.mean_diff.toFixed(4) }}</td><td>{{ row.t_stat.toFixed(4) }}</td>
                <td>{{ row.p_adj.toFixed(4) }}</td><td>{{ row.reject ? '✓' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Post-hoc between -->
        <div v-if="mixedAnovaData.postHocBetween?.length" class="section">
          <h4 class="subsection-title">Post-hoc comparisons (between-subjects, Bonferroni)</h4>
          <table class="data-table">
            <thead>
              <tr><th>Group 1</th><th>Group 2</th><th>Mean diff</th><th>p (adj)</th><th>Significant</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in mixedAnovaData.postHocBetween" :key="row.group1 + row.group2" :class="{ 'sig-row': row.reject }">
                <td>{{ row.group1 }}</td><td>{{ row.group2 }}</td>
                <td>{{ row.mean_diff.toFixed(4) }}</td><td>{{ row.p_adj.toFixed(4) }}</td><td>{{ row.reject ? '✓' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════════════════════════════
           Confirmatory Factor Analysis
           ═══════════════════════════════════════════════════════════════════ -->
      <div v-if="cfaData" class="section">
        <h3 class="section-title">CFA fit indices</h3>
        <div v-if="!cfaData.converged" class="warning-banner">
          ⚠ CFA model did not converge. Results may be unreliable.
        </div>
        <div class="fit-indices-grid">
          <div class="fit-card" :class="cfaData.rmsea <= 0.05 ? 'fit-good' : cfaData.rmsea <= 0.08 ? 'fit-acceptable' : 'fit-poor'">
            <div class="fit-card-label">RMSEA</div>
            <div class="fit-card-value">{{ cfaData.rmsea.toFixed(3) }}</div>
            <div class="fit-card-ci" v-if="cfaData.rmseaLower > 0">90% CI [{{ cfaData.rmseaLower.toFixed(3) }}, {{ cfaData.rmseaUpper.toFixed(3) }}]</div>
          </div>
          <div class="fit-card" :class="cfaData.cfi >= 0.95 ? 'fit-good' : cfaData.cfi >= 0.90 ? 'fit-acceptable' : 'fit-poor'">
            <div class="fit-card-label">CFI</div>
            <div class="fit-card-value">{{ cfaData.cfi.toFixed(3) }}</div>
          </div>
          <div class="fit-card" :class="cfaData.tli >= 0.95 ? 'fit-good' : cfaData.tli >= 0.90 ? 'fit-acceptable' : 'fit-poor'">
            <div class="fit-card-label">TLI</div>
            <div class="fit-card-value">{{ cfaData.tli.toFixed(3) }}</div>
          </div>
          <div class="fit-card" :class="cfaData.srmr <= 0.08 ? 'fit-good' : 'fit-poor'">
            <div class="fit-card-label">SRMR</div>
            <div class="fit-card-value">{{ cfaData.srmr.toFixed(3) }}</div>
          </div>
        </div>
        <p class="chi2-display">χ²({{ cfaData.df }}) = {{ cfaData.chi2.toFixed(2) }}, p = {{ cfaData.pValue.toFixed(4) }}</p>

        <!-- Loadings table -->
        <div v-if="cfaData.loadings.length" class="section">
          <h4 class="subsection-title">Standardized factor loadings</h4>
          <table class="data-table">
            <thead>
              <tr><th>Indicator</th><th>Factor</th><th>Loading</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in cfaData.loadings" :key="row.indicator">
                <td class="group-name">{{ row.indicator }}</td>
                <td>{{ row.factor }}</td>
                <td>{{ row.loading.toFixed(4) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Factor correlations -->
        <div v-if="cfaData.factorCorrelations?.length" class="section">
          <h4 class="subsection-title">Factor correlations</h4>
          <table class="data-table">
            <thead>
              <tr><th>Factor 1</th><th>Factor 2</th><th>Correlation</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in cfaData.factorCorrelations" :key="row.factor1 + row.factor2">
                <td>{{ row.factor1 }}</td><td>{{ row.factor2 }}</td>
                <td>{{ row.correlation.toFixed(4) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Effect size -->
      <div v-if="result.effect_size" class="effect-size-section">
        <span class="effect-label">{{ result.effect_size.name }}:</span>
        <strong>{{ result.effect_size.value.toFixed(3) }}</strong>
        <span class="effect-interp">({{ result.effect_size.interpretation }})</span>
      </div>

      <!-- Assumption checks -->
      <div v-if="result.assumption_checks.length" class="assumptions-section">
        <h3 class="section-title">Assumption checks</h3>
        <div
          v-for="check in result.assumption_checks"
          :key="check.name"
          class="check-item"
          :class="STATUS_CLASS[check.status]"
        >
          <span class="check-icon">{{ STATUS_ICON[check.status] }}</span>
          <div class="check-content">
            <div class="check-name">{{ check.name }}</div>
            <div class="check-detail">{{ check.detail }}</div>
            <div v-if="check.fix_suggestion" class="check-fix">{{ check.fix_suggestion }}</div>
          </div>
        </div>
      </div>

      <!-- Warnings -->
      <div v-if="result.warnings.length" class="warnings-section">
        <p v-for="w in result.warnings" :key="w" class="warning-item">⚠ {{ w }}</p>
      </div>

      <ExportPanel />
    </div>

    <div v-else class="no-result">
      <p class="no-result-primary">No result selected</p>
      <p class="no-result-secondary">Pick an analysis from the sidebar to view it here.</p>
    </div>
  </div>
</template>

<style scoped>
.results-view { display: flex; flex: 1; height: calc(100vh - var(--topbar-h)); overflow: hidden; }
.results-sidebar {
  width: 200px; flex-shrink: 0; border-right: 1px solid var(--color-border);
  padding: 16px 12px; display: flex; flex-direction: column; gap: 8px; overflow-y: auto;
}
.new-analysis-btn {
  background: var(--color-primary); color: #fff; border: none; border-radius: 8px;
  padding: 9px 12px; font-size: 13px; font-weight: 600; cursor: pointer; margin-bottom: 8px;
}
.history-label {
  font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--color-text-muted); padding: 4px 2px;
}
.history-item { font-size: 13px; padding: 6px 8px; border-radius: 6px; cursor: pointer; color: var(--color-text); transition: background 0.1s; }
.history-item:hover { background: var(--color-surface); }
.history-item.active { background: var(--color-accent-tint); color: var(--color-primary); font-weight: 600; }
.signin-nudge { font-size: 11px; color: var(--color-text-muted); border-top: 1px solid var(--color-border); padding-top: 10px; margin-top: auto; }
.results-main { flex: 1; overflow-y: auto; padding: 32px; display: flex; flex-direction: column; gap: 24px; }
.result-title { font-size: 22px; }
.result-meta { font-size: 13px; color: var(--color-text-muted); }

/* Headline cards */
.stats-cards { display: flex; flex-wrap: wrap; gap: 12px; }
.stat-card { border: 1px solid var(--color-border); border-radius: 10px; padding: 14px 18px; min-width: 120px; background: var(--color-surface); }
.stat-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-muted); margin-bottom: 4px; }
.stat-value { font-size: 18px; font-weight: 700; }

/* Section blocks */
.section { display: flex; flex-direction: column; gap: 12px; }
.section-title { font-size: 15px; font-weight: 600; margin: 0; }
.adjustment-badge { font-size: 12px; color: var(--color-text-muted); background: var(--color-surface); padding: 6px 10px; border-radius: 6px; border: 1px solid var(--color-border); }

/* Descriptive per-variable */
.var-block { display: flex; flex-direction: column; gap: 8px; }
.var-name { font-size: 14px; font-weight: 600; color: var(--color-primary); }
.desc-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.desc-cell { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 10px 14px; min-width: 100px; }
.desc-label { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--color-text-muted); margin-bottom: 3px; }
.desc-val { font-size: 16px; font-weight: 700; }

/* Tables */
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid var(--color-border); border-radius: 8px; overflow: hidden; }
.data-table th { text-align: left; padding: 8px 12px; background: var(--color-surface); border-bottom: 1px solid var(--color-border); font-weight: 600; color: var(--color-text-muted); font-size: 11px; text-transform: uppercase; }
.data-table td { padding: 7px 12px; border-bottom: 1px solid var(--color-border); }
.data-table tr:last-child td { border-bottom: none; }
.data-table .group-name { font-weight: 600; }
.sig-row td { background: var(--color-green-bg); }
.factor-heading { font-size: 13px; font-weight: 600; margin: 8px 0 4px; color: var(--color-primary); }
.bf-table { margin-bottom: 8px; }
.subtitle { font-size: 12px; font-weight: 400; color: var(--color-text-muted); margin-left: 6px; }

/* Effect size */
.effect-size-section { font-size: 14px; }
.effect-label { color: var(--color-text-muted); margin-right: 6px; }
.effect-interp { color: var(--color-text-muted); font-size: 13px; margin-left: 4px; }

/* Assumption checks */
.assumptions-section { display: flex; flex-direction: column; gap: 8px; }
.check-item { display: flex; gap: 10px; padding: 10px 14px; border-radius: 8px; font-size: 13px; border: 1px solid transparent; }
.check-pass { background: var(--color-green-bg); border-color: var(--color-green-border); }
.check-amber { background: var(--color-amber-bg); border-color: var(--color-amber-border); }
.check-fail { background: var(--color-red-bg); border-color: var(--color-red-border); }
.check-icon { font-weight: 700; font-size: 14px; flex-shrink: 0; }
.check-pass .check-icon { color: var(--color-green); }
.check-amber .check-icon { color: var(--color-amber); }
.check-fail .check-icon { color: var(--color-red); }
.check-name { font-weight: 600; }
.check-detail { color: var(--color-text-muted); margin-top: 2px; }
.check-fix { font-style: italic; margin-top: 4px; color: var(--color-text-muted); }

/* Interpretation */
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border); margin-bottom: 16px; }
.tab-btn { background: none; border: none; padding: 8px 14px; font-size: 13px; font-weight: 500; color: var(--color-text-muted); cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: color 0.15s; }
.tab-btn.active { color: var(--color-primary); border-bottom-color: var(--color-primary); }
.tab-content { font-size: 14px; line-height: 1.6; color: var(--color-text); }
.apa-text { font-style: italic; }
.mono-text { font-family: ui-monospace, monospace; font-size: 13px; }

/* Correlation matrix */
.corr-matrix-wrapper { overflow-x: auto; }
.corr-matrix { border-collapse: collapse; font-size: 13px; }
.corr-matrix th, .corr-matrix td { padding: 6px 10px; text-align: center; min-width: 70px; }
.corr-col-header, .corr-row-header { font-weight: 600; color: var(--color-text-muted); font-size: 12px; }
.corr-cell { border-radius: 0; font-variant-numeric: tabular-nums; }
.corr-diag { font-weight: 700; background: transparent !important; }

/* Warnings */
.warnings-section { display: flex; flex-direction: column; gap: 6px; }
.warning-item { font-size: 12px; color: var(--color-amber); background: var(--color-amber-bg); padding: 6px 10px; border-radius: 6px; }

.no-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 8px;
  text-align: center;
  padding: 48px 32px;
}
.no-result-primary { font-size: 16px; font-weight: 600; color: var(--color-text); margin: 0; }
.no-result-secondary { font-size: 13px; color: var(--color-text-muted); margin: 0; }

/* Panel regression */
.panel-model-badge {
  display: inline-block;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  padding: 6px 14px;
  border-radius: 20px;
  letter-spacing: 0.02em;
}
.panel-test-card {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}
.panel-test-row { display: flex; justify-content: space-between; }
.panel-test-label { color: var(--color-text-muted); font-weight: 600; }
.panel-timeline { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 0; }
.panel-timeline-step {
  position: relative;
  padding: 12px 16px 12px 32px;
  border-left: 2px solid var(--color-border);
}
.panel-timeline-step:first-child { padding-top: 0; }
.panel-timeline-step:last-child { border-left-color: transparent; }
.panel-timeline-step::before {
  content: '';
  position: absolute;
  left: -5px;
  top: 16px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
}
.panel-step-header { display: flex; justify-content: space-between; align-items: center; }
.panel-step-name { font-weight: 600; font-size: 13px; }
.panel-step-verdict { font-size: 12px; color: var(--color-text-muted); font-style: italic; }
.panel-step-detail { font-size: 12px; color: var(--color-text-muted); margin-top: 2px; }
.panel-step-outcome { font-size: 12px; margin-top: 4px; display: flex; align-items: center; gap: 6px; }
.model-pill {
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  padding: 2px 8px;
  border-radius: 10px;
}
.model-fe { background: #7c3aed; }
.model-re { background: #2563eb; }
.model-pooled_ols { background: #6b7280; }
.panel-absorbed-note { font-size: 13px; color: var(--color-text-muted); }
.jn-text { font-size: 14px; line-height: 1.6; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 12px 16px; }
/* Time-series */
.stationarity-grid { display: flex; flex-wrap: wrap; gap: 12px; }
.test-card {
  border: 1px solid var(--color-border); border-radius: 8px; padding: 12px 16px;
  min-width: 160px; flex: 1; display: flex; flex-direction: column; gap: 4px;
}
.test-pass { background: var(--color-green-bg); border-color: var(--color-green-border); }
.test-fail { background: var(--color-red-bg); border-color: var(--color-red-border); }
.test-card-title { font-weight: 700; font-size: 14px; }
.test-card-stat { font-size: 13px; color: var(--color-text-muted); }
.test-card-verdict { font-size: 12px; font-weight: 700; margin-top: 4px; }
.ljung-box-card {
  border: 1px solid var(--color-border); border-radius: 8px;
  padding: 10px 14px; font-size: 13px; display: flex; gap: 8px;
  background: var(--color-surface);
}
.ljung-box-label { font-weight: 600; color: var(--color-text-muted); }
.acf-table-wrapper { overflow-x: auto; }
.acf-table { border-collapse: collapse; font-size: 13px; width: 100%; border: 1px solid var(--color-border); }
.acf-table th { text-align: left; padding: 6px 10px; background: var(--color-surface); border-bottom: 1px solid var(--color-border); font-size: 11px; text-transform: uppercase; color: var(--color-text-muted); }
.acf-table td { padding: 4px 10px; border-bottom: 1px solid var(--color-border); }
.acf-lag, .acf-val { font-variant-numeric: tabular-nums; }
.acf-spark { width: 80px; }
.spark-text { font-size: 14px; letter-spacing: 0.5px; color: var(--color-primary); }
.seasonal-card {
  border: 1px solid var(--color-border); border-radius: 8px;
  padding: 12px 16px; display: flex; flex-direction: column; gap: 6px; font-size: 13px;
}
.seasonal-row { display: flex; justify-content: space-between; }
.seasonal-label { font-weight: 600; color: var(--color-text-muted); }
.arima-card {
  border: 1px solid var(--color-border); border-radius: 8px;
  padding: 12px 16px; display: flex; flex-direction: column; gap: 6px; font-size: 13px;
}
.arima-row { display: flex; justify-content: space-between; }
.arima-label { font-weight: 600; color: var(--color-text-muted); }
.arima-value { font-weight: 700; color: var(--color-primary); }
.forecast-wrapper { overflow-x: auto; }
.forecast-table { border-collapse: collapse; font-size: 13px; width: 100%; border: 1px solid var(--color-border); }
.forecast-table th { text-align: left; padding: 6px 10px; background: var(--color-surface); border-bottom: 1px solid var(--color-border); font-size: 11px; text-transform: uppercase; color: var(--color-text-muted); }
.forecast-table td { padding: 4px 10px; border-bottom: 1px solid var(--color-border); }
.fcast-step, .fcast-val, .fcast-ci { font-variant-numeric: tabular-nums; }
.fcast-spark { width: 100px; }
.spark-range { font-size: 14px; display: flex; align-items: center; gap: 2px; }
.spark-dot { font-size: 6px; color: var(--color-primary); }

.mediation-badge { font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 10px; text-transform: capitalize; }
.mediation-none { background: var(--surface-2); color: var(--color-text-secondary); }
.mediation-partial { background: var(--color-amber-bg); color: var(--color-amber); }
.mediation-full { background: var(--color-green-bg); color: var(--color-green); }

/* VIF badges */
.vif-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 10px; }
.vif-concern { background: var(--color-red-bg); color: var(--color-red); }
.vif-examine { background: var(--color-amber-bg); color: var(--color-amber); }
.vif-ok { background: var(--color-green-bg); color: var(--color-green); }

/* Robustness card */
.robustness-card {
  border: 1px solid var(--color-border); border-radius: 8px;
  padding: 12px 16px; display: flex; flex-direction: column; gap: 6px;
  font-size: 13px;
}
.robustness-row { display: flex; justify-content: space-between; }
.robustness-label { color: var(--color-text-muted); font-weight: 600; }
.robustness-value { color: var(--color-text); }
.robustness-citation { font-size: 12px; color: var(--color-text-muted); margin-top: 4px; font-style: italic; }

/* Remediation patterns */
.remediation-patterns { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.pattern-card {
  border-radius: 6px; padding: 12px 16px;
  border: 1px solid var(--color-border);
}
.pattern-high { background: var(--color-red-bg); border-left: 4px solid var(--color-red); }
.pattern-medium { background: var(--color-amber-bg); border-left: 4px solid var(--color-amber); }
.pattern-low { background: var(--color-accent-tint); border-left: 4px solid var(--color-accent); }
.pattern-title { font-weight: 700; font-size: 13px; margin-bottom: 4px; }
.pattern-interp { font-size: 13px; color: var(--color-text-muted); margin-bottom: 6px; }
.pattern-rec { font-size: 13px; font-style: italic; color: var(--color-text); }

/* Remedy cards */
.remedy-group { margin-bottom: 16px; }
.remedy-group-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.remedy-verdict-badge { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.04em; }
.verdict-fail { background: var(--color-red-bg); color: var(--color-red); }
.verdict-borderline { background: var(--color-amber-bg); color: var(--color-amber); }
.remedy-card {
  border: 1px solid var(--color-border); border-radius: 6px;
  padding: 10px 14px; margin-bottom: 8px; font-size: 13px;
}
.remedy-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.remedy-num { color: var(--color-text-muted); font-size: 12px; min-width: 20px; }
.remedy-desc { font-weight: 500; }
.remedy-kind { font-size: 10px; font-weight: 700; padding: 1px 7px; border-radius: 8px; margin-left: auto; }
.kind-quick_fix { background: var(--color-green-bg); color: var(--color-green); }
.kind-thinking_fix { background: var(--surface-2); color: var(--color-text-muted); }
.remedy-why { font-size: 12px; color: var(--color-text-muted); margin-left: 28px; }
.remedy-caveat {
  font-size: 12px; color: var(--color-amber); background: var(--color-amber-bg);
  border: 1px solid var(--color-amber-border); border-radius: 6px;
  padding: 8px 12px; margin-bottom: 10px;
}

/* Survival */
.survival-stats-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.test-card { flex: 1; min-width: 160px; padding: 12px; border-radius: 8px; border: 1px solid var(--color-border); background: var(--color-surface); }
.test-card-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-muted); margin-bottom: 4px; }
.test-card-stat { font-size: 13px; color: var(--color-text); }
.test-card-verdict { font-size: 12px; font-weight: 600; margin-top: 4px; }
.chart-wrapper { height: 320px; padding: 12px 0; }
.warning-banner { background: var(--color-amber-bg); border: 1px solid var(--color-amber-border); color: var(--color-amber); padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; font-size: 13px; }
.cox-fit-card { margin-top: 10px; padding: 8px 12px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 6px; font-size: 13px; }
.cox-fit-label { color: var(--color-text-muted); }

/* Mixed ANOVA */
.subsection-title { font-size: 13px; font-weight: 600; color: var(--color-text-muted); margin: 0 0 8px; }
.sphericity-card { padding: 12px; border-radius: 8px; border: 1px solid var(--color-border); margin-bottom: 12px; }

/* CFA */
.fit-indices-grid { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
.fit-card { flex: 1; min-width: 120px; padding: 14px; border-radius: 8px; border: 1px solid var(--color-border); text-align: center; }
.fit-card-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-muted); margin-bottom: 4px; }
.fit-card-value { font-size: 24px; font-weight: 700; }
.fit-card-ci { font-size: 11px; color: var(--color-text-muted); margin-top: 2px; }
.fit-good { border-color: var(--color-green-border); background: var(--color-green-bg); }
.fit-acceptable { border-color: var(--color-amber-border); background: var(--color-amber-bg); }
.fit-poor { border-color: var(--color-red-border); background: var(--color-red-bg); }
.chi2-display { font-size: 13px; color: var(--color-text-muted); margin: 0 0 12px; }
</style>
