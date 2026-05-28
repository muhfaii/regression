import type { TestDefinition } from '../types/analysis'

export const TEST_CATALOG: TestDefinition[] = [
  // ── Descriptive ────────────────────────────────────────────────────────────
  {
    key: 'descriptive',
    name: 'Descriptive Statistics',
    category: 'Descriptive',
    descriptor: 'mean, SD, summary',
    tooltip: 'Summarises your data with means, standard deviations, and distribution shape.',
    slots: [{ key: 'variables', label: 'Variables', required_type: 'any', multiple: true }],
  },

  // ── Compare groups ─────────────────────────────────────────────────────────
  {
    key: 'independent_t',
    name: 'Independent t-test',
    category: 'Compare groups',
    descriptor: '2 groups, continuous',
    tooltip: 'Tests whether two independent groups have different means on a continuous outcome.',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'group', label: 'Group variable', required_type: 'categorical', multiple: false },
    ],
  },
  {
    key: 'paired_t',
    name: 'Paired t-test',
    category: 'Compare groups',
    descriptor: '2 conditions, paired',
    tooltip: 'Tests whether means differ across two related measurements (e.g. pre vs. post).',
    slots: [
      { key: 'col_a', label: 'Measurement A', required_type: 'continuous', multiple: false },
      { key: 'col_b', label: 'Measurement B', required_type: 'continuous', multiple: false },
    ],
  },
  {
    key: 'one_way_anova',
    name: 'One-way ANOVA',
    category: 'Compare groups',
    descriptor: '3+ groups',
    tooltip: 'Tests whether three or more independent groups have different means.',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'group', label: 'Group variable', required_type: 'categorical', multiple: false },
    ],
  },
  {
    key: 'factorial_anova',
    name: 'Factorial ANOVA',
    category: 'Compare groups',
    descriptor: '2+ factors',
    tooltip: 'Tests the effects of two or more categorical factors and their interactions on a continuous outcome.',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'factors', label: 'Factor variables', required_type: 'categorical', multiple: true },
    ],
  },
  {
    key: 'mann_whitney',
    name: 'Mann-Whitney U',
    category: 'Compare groups',
    descriptor: '2 groups, non-param',
    tooltip: 'Non-parametric alternative to the independent t-test when data is not normally distributed.',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'group', label: 'Group variable', required_type: 'categorical', multiple: false },
    ],
  },
  {
    key: 'wilcoxon',
    name: 'Wilcoxon Signed-Rank',
    category: 'Compare groups',
    descriptor: 'paired, non-param',
    tooltip: 'Non-parametric alternative to the paired t-test for non-normal paired data.',
    slots: [
      { key: 'col_a', label: 'Measurement A', required_type: 'continuous', multiple: false },
      { key: 'col_b', label: 'Measurement B', required_type: 'continuous', multiple: false },
    ],
  },
  {
    key: 'kruskal_wallis',
    name: 'Kruskal-Wallis',
    category: 'Compare groups',
    descriptor: '3+ groups, non-param',
    tooltip: 'Non-parametric alternative to one-way ANOVA for non-normal data.',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'group', label: 'Group variable', required_type: 'categorical', multiple: false },
    ],
  },

  // ── Relationships ──────────────────────────────────────────────────────────
  {
    key: 'correlation',
    name: 'Correlation',
    category: 'Relationships',
    descriptor: 'Pearson/Spearman/Kendall',
    tooltip: 'Measures pairwise relationships between 2+ variables with Pearson, Spearman, and Kendall coefficients.',
    slots: [
      { key: 'variables', label: 'Variables', required_type: 'continuous', multiple: true },
    ],
  },
  {
    key: 'chi_square',
    name: 'Chi-square',
    category: 'Relationships',
    descriptor: 'categorical association',
    tooltip: 'Tests whether two categorical variables are statistically independent.',
    slots: [
      { key: 'col_a', label: 'Variable A', required_type: 'categorical', multiple: false },
      { key: 'col_b', label: 'Variable B', required_type: 'categorical', multiple: false },
    ],
  },

  // ── Regression ─────────────────────────────────────────────────────────────
  {
    key: 'ols_regression',
    name: 'OLS Regression',
    category: 'Regression',
    descriptor: 'linear, continuous outcome',
    tooltip: 'Estimates the linear relationship between a continuous outcome and one or more predictors.',
    slots: [
      { key: 'dep_var', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'indep_vars', label: 'Predictor variables', required_type: 'any', multiple: true },
    ],
  },
  {
    key: 'panel_regression',
    name: 'Panel Regression (FE/RE)',
    category: 'Regression',
    descriptor: 'panel data, entity-time',
    tooltip: 'Estimates panel data models with automatic FE/RE/Pooled selection, BP-LM and Hausman tests.',
    slots: [
      { key: 'dep_var', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'indep_vars', label: 'Predictor variables', required_type: 'any', multiple: true },
      { key: 'entity_col', label: 'Entity column', required_type: 'any', multiple: false },
      { key: 'time_col', label: 'Time column', required_type: 'any', multiple: false },
    ],
  },
  {
    key: 'logistic_regression',
    name: 'Logistic Regression',
    category: 'Regression',
    descriptor: 'binary outcome',
    tooltip: 'Predicts the probability of a binary outcome from one or more predictor variables.',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'categorical', multiple: false },
      { key: 'predictors', label: 'Predictor variables', required_type: 'any', multiple: true },
    ],
  },
  {
    key: 'moderation',
    name: 'Moderation Analysis',
    category: 'Regression',
    descriptor: 'interaction effects',
    tooltip: 'Tests whether the relationship between a predictor and outcome depends on a third variable (moderator).',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'predictor', label: 'Predictor variable', required_type: 'any', multiple: false },
      { key: 'moderator', label: 'Moderator variable', required_type: 'any', multiple: false },
      { key: 'covariates', label: 'Covariates (optional)', required_type: 'any', multiple: true },
    ],
  },
  {
    key: 'mediation',
    name: 'Mediation Analysis',
    category: 'Regression',
    descriptor: 'indirect effects',
    tooltip: 'Tests whether the relationship between a predictor and outcome is mediated through a third variable.',
    slots: [
      { key: 'outcome', label: 'Outcome variable', required_type: 'continuous', multiple: false },
      { key: 'predictor', label: 'Predictor variable', required_type: 'any', multiple: false },
      { key: 'mediator', label: 'Mediator variable', required_type: 'any', multiple: false },
      { key: 'covariates', label: 'Covariates (optional)', required_type: 'any', multiple: true },
    ],
  },

  // ── Advanced (coming soon) ─────────────────────────────────────────────────
  {
    key: 'mixed_anova',
    name: 'Mixed ANOVA',
    category: 'Advanced',
    descriptor: 'between + within factors',
    tooltip: 'Analyses designs with both between-subjects and within-subjects factors.',
    slots: [],
    coming_soon: true,
  },
  {
    key: 'sem',
    name: 'Structural Equation Modelling',
    category: 'Advanced',
    descriptor: 'latent variables',
    tooltip: 'Models complex relationships between latent and observed variables simultaneously.',
    slots: [],
    coming_soon: true,
  },
  {
    key: 'multilevel',
    name: 'Multilevel Modelling',
    category: 'Advanced',
    descriptor: 'nested data',
    tooltip: 'Accounts for nested or hierarchical data structures (students within schools, etc.).',
    slots: [],
    coming_soon: true,
  },
]

export const TEST_CATEGORIES = [...new Set(TEST_CATALOG.map(t => t.category))]

export function getTest(key: string): TestDefinition | undefined {
  return TEST_CATALOG.find(t => t.key === key)
}
