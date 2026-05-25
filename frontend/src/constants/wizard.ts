// Deterministic Guide Me routing table.
// Each entry: [q1, q2, q3, q4] → test_key
// null = "I'm not sure" wildcard

export type WizardAnswers = [string | null, string | null, string | null, string | null]

interface RoutingEntry {
  answers: WizardAnswers
  test_key: string
  reason: string
}

export const ROUTING_TABLE: RoutingEntry[] = [
  // Compare + 2 groups + continuous + normal → independent t-test
  { answers: ['compare', '2', 'continuous', 'yes'], test_key: 'independent_t', reason: 'You want to compare the means of two groups on a continuous, normally distributed outcome.' },
  // Compare + 2 groups + continuous + not normal → Mann-Whitney
  { answers: ['compare', '2', 'continuous', 'no'], test_key: 'mann_whitney', reason: 'Your outcome is continuous but not normally distributed, so a non-parametric test is more appropriate.' },
  { answers: ['compare', '2', 'continuous', null], test_key: 'independent_t', reason: 'You want to compare two groups on a continuous outcome.' },
  // Compare + 3+ groups + continuous + normal → ANOVA
  { answers: ['compare', '3+', 'continuous', 'yes'], test_key: 'one_way_anova', reason: 'You have three or more groups and a continuous, normally distributed outcome — ANOVA is the right choice.' },
  // Compare + 3+ groups + continuous + not normal → Kruskal-Wallis
  { answers: ['compare', '3+', 'continuous', 'no'], test_key: 'kruskal_wallis', reason: 'You have three or more groups but your data is not normally distributed, so a non-parametric alternative is better.' },
  { answers: ['compare', '3+', 'continuous', null], test_key: 'one_way_anova', reason: 'You want to compare three or more groups on a continuous outcome.' },
  // Compare + 2 groups + categorical → chi-square
  { answers: ['compare', '2', 'categorical', null], test_key: 'chi_square', reason: 'Your outcome is categorical, so chi-square tests the association between the group and the outcome.' },
  { answers: ['compare', '3+', 'categorical', null], test_key: 'chi_square', reason: 'Your outcome is categorical, so chi-square tests the association between the group and the outcome.' },
  // Compare + paired
  { answers: ['compare', 'paired', 'continuous', 'yes'], test_key: 'paired_t', reason: 'You are comparing paired measurements and your data is normally distributed.' },
  { answers: ['compare', 'paired', 'continuous', 'no'], test_key: 'wilcoxon', reason: 'You are comparing paired measurements but your data is not normally distributed.' },
  { answers: ['compare', 'paired', 'continuous', null], test_key: 'paired_t', reason: 'You are comparing paired measurements on a continuous outcome.' },
  // Describe → descriptive statistics
  { answers: ['describe', null, null, null], test_key: 'descriptive', reason: 'You want to summarise your data — descriptive statistics will give you means, variability, and distribution shape.' },
  // Relate + continuous → correlation
  { answers: ['relate', null, 'continuous', null], test_key: 'correlation', reason: 'You want to measure the relationship between two continuous variables.' },
  { answers: ['relate', null, 'categorical', null], test_key: 'chi_square', reason: 'You want to test the association between two categorical variables.' },
  { answers: ['relate', null, null, null], test_key: 'correlation', reason: 'You want to explore the relationship between two variables.' },
  // Predict → OLS regression
  { answers: ['predict', null, 'continuous', null], test_key: 'ols_regression', reason: 'You want to predict a continuous outcome from one or more variables — OLS regression is the standard approach.' },
  { answers: ['predict', null, 'categorical', null], test_key: 'logistic_regression', reason: 'You want to predict a categorical (binary) outcome — logistic regression models the probability of each class.' },
  { answers: ['predict', null, null, null], test_key: 'ols_regression', reason: 'You want to predict an outcome from other variables.' },
  // Fallback
  { answers: [null, null, null, null], test_key: 'descriptive', reason: 'Start with descriptive statistics to explore your data before choosing an inferential test.' },
]

export const WIZARD_QUESTIONS = [
  {
    step: 1,
    question: 'What are you trying to find out?',
    options: [
      { value: 'compare', label: 'Compare groups', hint: 'e.g. do men and women differ in scores?' },
      { value: 'describe', label: 'Describe my data', hint: 'e.g. what is the average score, how spread out is it?' },
      { value: 'relate', label: 'Explore a relationship', hint: 'e.g. does studying more relate to higher scores?' },
      { value: 'predict', label: 'Predict an outcome', hint: 'e.g. which factors predict exam success?' },
      { value: null, label: "I'm not sure" },
    ],
  },
  {
    step: 2,
    question: 'How many groups are you comparing?',
    options: [
      { value: '2', label: 'Two groups', hint: 'e.g. control vs treatment' },
      { value: '3+', label: 'Three or more groups', hint: 'e.g. low, medium, high dose' },
      { value: 'paired', label: 'Same participants, two conditions', hint: 'e.g. before and after' },
      { value: null, label: "I'm not sure" },
    ],
  },
  {
    step: 3,
    question: 'What type is your outcome variable?',
    options: [
      { value: 'continuous', label: 'Continuous', hint: 'e.g. scores, time, weight' },
      { value: 'categorical', label: 'Categorical', hint: 'e.g. pass/fail, yes/no, political party' },
      { value: null, label: "I'm not sure" },
    ],
  },
  {
    step: 4,
    question: 'Is your data roughly normally distributed?',
    options: [
      { value: 'yes', label: 'Yes, approximately normal' },
      { value: 'no', label: 'No, or I think it might be skewed' },
      { value: null, label: "I'm not sure" },
    ],
  },
]

export function resolveTest(answers: WizardAnswers): { test_key: string; reason: string } {
  // Exact match first
  for (const entry of ROUTING_TABLE) {
    if (entry.answers.every((a, i) => a === answers[i])) {
      return { test_key: entry.test_key, reason: entry.reason }
    }
  }
  // Wildcard match: entry nulls are wildcards
  for (const entry of ROUTING_TABLE) {
    if (entry.answers.every((a, i) => a === null || a === answers[i])) {
      return { test_key: entry.test_key, reason: entry.reason }
    }
  }
  return { test_key: 'descriptive', reason: 'Start with descriptive statistics to explore your data.' }
}
