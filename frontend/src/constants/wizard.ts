// Deterministic Guide Me routing engine.
//
// The wizard has one root question (branch selector) followed by a
// branch-specific sequence of questions. Each branch computes its own step
// list from the answers collected so far (so irrelevant questions — e.g.
// "is it normally distributed?" for a categorical outcome — are skipped),
// and resolves to a recommended test once its steps are exhausted.

export type Answers = Record<string, string | null>

export interface WizardOption {
  value: string | null
  label: string
  hint?: string
}

export interface WizardQuestion {
  id: string
  question: string
  options: WizardOption[]
}

export interface Recommendation {
  test_key: string
  reason: string
}

interface Branch {
  getSteps(answers: Answers): WizardQuestion[]
  resolve(answers: Answers): Recommendation
}

const NOT_SURE: WizardOption = { value: null, label: "I'm not sure" }

export const ROOT_QUESTION: WizardQuestion = {
  id: 'goal',
  question: 'What are you trying to find out?',
  options: [
    { value: 'compare', label: 'Compare groups', hint: 'e.g. do men and women differ in scores?' },
    { value: 'describe', label: 'Describe my data', hint: 'e.g. what is the average score, how spread out is it?' },
    { value: 'relate', label: 'Explore a relationship', hint: 'e.g. does studying more relate to higher scores?' },
    { value: 'predict', label: 'Predict or explain an outcome', hint: 'e.g. which factors predict exam success' },
    { value: 'structure', label: 'Examine a scale or set of related variables', hint: 'e.g. do these survey items measure one trait?' },
    { value: 'change', label: 'Analyze change over time', hint: 'e.g. sales trends, time until an event happens' },
    NOT_SURE,
  ],
}

// ---------------------------------------------------------------------------
// Shared question fragments
// ---------------------------------------------------------------------------

const OUTCOME_TYPE_Q: WizardQuestion = {
  id: 'outcome_type',
  question: 'What type is your outcome variable?',
  options: [
    { value: 'continuous', label: 'Continuous', hint: 'e.g. scores, time, weight' },
    { value: 'categorical', label: 'Categorical', hint: 'e.g. pass/fail, yes/no, political party' },
    NOT_SURE,
  ],
}

const NORMAL_Q: WizardQuestion = {
  id: 'normal',
  question: 'Is your data roughly normally distributed?',
  options: [
    { value: 'yes', label: 'Yes, approximately normal' },
    { value: 'no', label: 'No, or I think it might be skewed' },
    NOT_SURE,
  ],
}

// ---------------------------------------------------------------------------
// Branches
// ---------------------------------------------------------------------------

const BRANCHES: Record<string, Branch> = {
  compare: {
    getSteps(a) {
      const designQ: WizardQuestion = {
        id: 'design',
        question: "What's your comparison design?",
        options: [
          { value: '2', label: 'Two independent groups', hint: 'e.g. control vs treatment' },
          { value: '3+', label: 'Three or more independent groups', hint: 'e.g. low, medium, high dose' },
          { value: 'factorial', label: 'Two or more grouping factors', hint: 'e.g. treatment × gender' },
          { value: 'repeated', label: 'Same participants, multiple time points', hint: 'e.g. pre / mid / post' },
          { value: 'paired', label: 'Same participants, two conditions', hint: 'e.g. before and after' },
          NOT_SURE,
        ],
      }
      if (a.design === 'factorial' || a.design === 'repeated') return [designQ]
      const steps = [designQ, OUTCOME_TYPE_Q]
      if (a.outcome_type === 'categorical') return steps
      return [...steps, NORMAL_Q]
    },
    resolve(a) {
      if (a.design === 'factorial') {
        return { test_key: 'factorial_anova', reason: 'You have two or more grouping factors — factorial ANOVA tests their individual and interaction effects.' }
      }
      if (a.design === 'repeated') {
        return { test_key: 'mixed_anova', reason: 'You are measuring the same participants across multiple time points or conditions — mixed ANOVA handles within-subjects designs.' }
      }
      if (a.outcome_type === 'categorical') {
        return { test_key: 'chi_square', reason: 'Your outcome is categorical, so chi-square tests the association between the group and the outcome.' }
      }
      const normal = a.normal
      if (a.design === '2') {
        return normal === 'no'
          ? { test_key: 'mann_whitney', reason: 'Your outcome is continuous but not normally distributed, so a non-parametric test is more appropriate.' }
          : { test_key: 'independent_t', reason: 'You want to compare the means of two groups on a continuous outcome.' }
      }
      if (a.design === '3+') {
        return normal === 'no'
          ? { test_key: 'kruskal_wallis', reason: 'You have three or more groups but your data is not normally distributed, so a non-parametric alternative is better.' }
          : { test_key: 'one_way_anova', reason: 'You have three or more groups and a continuous outcome — ANOVA is the right choice.' }
      }
      if (a.design === 'paired') {
        return normal === 'no'
          ? { test_key: 'wilcoxon', reason: 'You are comparing paired measurements but your data is not normally distributed.' }
          : { test_key: 'paired_t', reason: 'You are comparing paired measurements on a continuous, normally distributed outcome.' }
      }
      return { test_key: 'independent_t', reason: 'You want to compare groups on a continuous outcome.' }
    },
  },

  describe: {
    getSteps() {
      return []
    },
    resolve() {
      return { test_key: 'descriptive', reason: 'You want to summarise your data — descriptive statistics will give you means, variability, and distribution shape.' }
    },
  },

  relate: {
    getSteps() {
      return [{
        id: 'outcome_type',
        question: 'What type are the variables you want to relate?',
        options: OUTCOME_TYPE_Q.options,
      }]
    },
    resolve(a) {
      if (a.outcome_type === 'categorical') {
        return { test_key: 'chi_square', reason: 'You want to test the association between two categorical variables.' }
      }
      return { test_key: 'correlation', reason: 'You want to measure the relationship between two or more continuous variables.' }
    },
  },

  predict: {
    getSteps(a) {
      const kindQ: WizardQuestion = {
        id: 'predict_kind',
        question: 'What kind of predictive question is it?',
        options: [
          { value: 'simple', label: 'Predict an outcome from one or more variables', hint: 'standard regression' },
          { value: 'panel', label: 'Predict using repeated observations over time', hint: 'entities measured across time periods' },
          { value: 'moderation', label: 'Test whether a third variable changes the relationship', hint: 'interaction / moderation effect' },
          { value: 'mediation', label: 'Test whether the effect works through another variable', hint: 'indirect / mediation effect' },
          NOT_SURE,
        ],
      }
      if (a.predict_kind === 'simple' || a.predict_kind == null) return [kindQ, OUTCOME_TYPE_Q]
      return [kindQ]
    },
    resolve(a) {
      if (a.predict_kind === 'panel') {
        return { test_key: 'panel_regression', reason: 'Your data has repeated observations per entity over time — panel regression accounts for that structure.' }
      }
      if (a.predict_kind === 'moderation') {
        return { test_key: 'moderation', reason: 'You want to test whether a third variable changes the strength or direction of a relationship.' }
      }
      if (a.predict_kind === 'mediation') {
        return { test_key: 'mediation', reason: 'You want to test whether a predictor affects the outcome indirectly, through another variable.' }
      }
      if (a.outcome_type === 'categorical') {
        return { test_key: 'logistic_regression', reason: 'You want to predict a categorical (binary) outcome — logistic regression models the probability of each class.' }
      }
      return { test_key: 'ols_regression', reason: 'You want to predict a continuous outcome from one or more variables — OLS regression is the standard approach.' }
    },
  },

  structure: {
    getSteps() {
      return [{
        id: 'structure_kind',
        question: 'What do you want to check?',
        options: [
          { value: 'reliability', label: 'How consistent a scale is', hint: "e.g. Cronbach's alpha for a survey" },
          { value: 'efa', label: "Discover a scale's underlying structure", hint: "you don't know the factors yet" },
          { value: 'cfa', label: 'Confirm a specific, pre-defined structure', hint: 'you already have a hypothesized factor model' },
          NOT_SURE,
        ],
      }]
    },
    resolve(a) {
      if (a.structure_kind === 'cfa') {
        return { test_key: 'cfa', reason: 'You have a pre-specified factor structure to confirm — confirmatory factor analysis tests how well it fits.' }
      }
      if (a.structure_kind === 'efa') {
        return { test_key: 'factor_analysis', reason: 'You want to discover the underlying structure in your variables — exploratory factor analysis identifies latent factors.' }
      }
      return { test_key: 'reliability', reason: 'You want to check how consistently a set of items measures the same underlying construct.' }
    },
  },

  change: {
    getSteps() {
      return [{
        id: 'change_kind',
        question: 'What kind of data do you have?',
        options: [
          { value: 'series', label: 'Values measured repeatedly over time', hint: 'e.g. monthly sales, daily temperature' },
          { value: 'event', label: 'Time until an event happens', hint: 'e.g. time to failure, patient survival' },
          NOT_SURE,
        ],
      }]
    },
    resolve(a) {
      if (a.change_kind === 'event') {
        return { test_key: 'survival_analysis', reason: 'You want to analyse time until an event occurs — survival analysis handles censored time-to-event data.' }
      }
      return { test_key: 'timeseries', reason: 'You want to analyse a value measured repeatedly over time — time-series methods model trend, seasonality, and forecasts.' }
    },
  },
}

const FALLBACK: Recommendation = { test_key: 'descriptive', reason: 'Start with descriptive statistics to explore your data before choosing an inferential test.' }

export function getBranch(goal: string | null): Branch | null {
  if (goal == null) return null
  return BRANCHES[goal] ?? null
}

export function resolveTest(goal: string | null, answers: Answers): Recommendation {
  const branch = getBranch(goal)
  if (!branch) return FALLBACK
  return branch.resolve(answers)
}
