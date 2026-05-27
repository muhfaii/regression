<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useResultsStore } from '../stores/results'
import { useSessionStore } from '../stores/session'
import ExportPanel from '../components/results/ExportPanel.vue'

const router = useRouter()
const results = useResultsStore()
const session = useSessionStore()

const result = computed(() => results.activeResult)
const activeTab = ref<'plain' | 'apa' | 'technical'>(
  session.mode === 'browse' ? 'technical' : 'plain'
)

const STATUS_ICON: Record<string, string> = { pass: '✓', amber: '⚠', fail: '✗' }
const STATUS_CLASS: Record<string, string> = { pass: 'check-pass', amber: 'check-amber', fail: 'check-fail' }

// Top-level scalar keys rendered as headline cards (skip structural sub-objects)
const SKIP_KEYS = new Set(['variables', 'groups', 'coefficients', 'post_hoc', 'contingency_table', 'outcome_categories'])

function scalarCards(stats: Record<string, unknown>) {
  return Object.entries(stats).filter(([k, v]) =>
    !SKIP_KEYS.has(k) && (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean')
  )
}

function fmt(val: unknown): string {
  if (typeof val === 'number') return Number.isInteger(val) ? String(val) : val.toFixed(4)
  if (typeof val === 'boolean') return val ? 'Yes' : 'No'
  return String(val)
}

function fmtLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// Descriptive stats: statistics.variables
const descriptiveVars = computed(() => {
  if (result.value?.test_key !== 'descriptive') return null
  return result.value.statistics.variables as Record<string, Record<string, number>>
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
  return c as Record<string, Record<string, number>>
})

// Post-hoc: statistics.post_hoc
const postHoc = computed(() => {
  const ph = result.value?.statistics?.post_hoc
  if (!Array.isArray(ph) || ph.length === 0) return null
  return ph as { group1: string; group2: string; mean_diff: number; p_adj: number; reject: boolean }[]
})

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
      <p class="signin-nudge">Sign in to save history across sessions.</p>
    </aside>

    <!-- Main results -->
    <div v-if="result" class="results-main">
      <h1 class="result-title">{{ result.test_name }}</h1>
      <p class="result-meta">N = {{ result.n_obs }}</p>

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
              <th v-for="col in Object.keys(Object.values(coefficients)[0])" :key="col">{{ fmtLabel(col) }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(stats, pred) in coefficients" :key="pred">
              <td class="group-name">{{ pred }}</td>
              <td v-for="val in Object.values(stats)" :key="String(val)">{{ fmt(val) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Post-hoc table -->
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

      <!-- Interpretation tabs -->
      <div class="interpretation-section">
        <h3 class="section-title">Interpretation</h3>
        <div class="tabs">
          <button
            v-for="[key, label] in ([['plain', 'Plain English'], ['apa', 'APA 7'], ['technical', 'Technical']] as [string, string][])"
            :key="key"
            class="tab-btn"
            :class="{ active: activeTab === key }"
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

      <!-- Warnings -->
      <div v-if="result.warnings.length" class="warnings-section">
        <p v-for="w in result.warnings" :key="w" class="warning-item">⚠ {{ w }}</p>
      </div>

      <ExportPanel />
    </div>

    <div v-else class="no-result">No result selected.</div>
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
.history-item.active { background: #ede9fe; color: var(--color-primary); font-weight: 600; }
.signin-nudge { font-size: 11px; color: var(--color-text-muted); border-top: 1px solid var(--color-border); padding-top: 10px; margin-top: auto; }
.results-main { flex: 1; overflow-y: auto; padding: 32px; display: flex; flex-direction: column; gap: 24px; max-width: 860px; }
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
.sig-row td { background: #f0fdf4; }

/* Effect size */
.effect-size-section { font-size: 14px; }
.effect-label { color: var(--color-text-muted); margin-right: 6px; }
.effect-interp { color: var(--color-text-muted); font-size: 13px; margin-left: 4px; }

/* Assumption checks */
.assumptions-section { display: flex; flex-direction: column; gap: 8px; }
.check-item { display: flex; gap: 10px; padding: 10px 14px; border-radius: 8px; font-size: 13px; border: 1px solid transparent; }
.check-pass { background: var(--color-green-bg); border-color: #bbf7d0; }
.check-amber { background: var(--color-amber-bg); border-color: #fde68a; }
.check-fail { background: #fef2f2; border-color: #fecaca; }
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

/* Warnings */
.warnings-section { display: flex; flex-direction: column; gap: 6px; }
.warning-item { font-size: 12px; color: var(--color-amber); background: var(--color-amber-bg); padding: 6px 10px; border-radius: 6px; }

.no-result { display: flex; align-items: center; justify-content: center; flex: 1; color: var(--color-text-muted); }
</style>
