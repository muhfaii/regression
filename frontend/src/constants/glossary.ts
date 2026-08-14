// Plain-language definitions for statistical terms shown in results.
// Keyed to match the labels used in ResultsView (LABEL_MAP keys plus a few
// standalone table-column terms). Missing keys simply render without a tooltip.

export const GLOSSARY: Record<string, string> = {
  r_squared: 'The proportion of variance in the outcome explained by the model, from 0 (none) to 1 (all of it).',
  adj_r_squared: 'R² adjusted for the number of predictors, so adding useless variables doesn\'t inflate it.',
  f_statistic: 'A ratio comparing explained to unexplained variance. Larger values suggest the model fits better than chance.',
  p_value: 'The probability of seeing a result this extreme if there were truly no effect. Conventionally, below 0.05 is considered statistically significant.',
  n_obs: 'The number of observations (rows) used in the analysis.',
  chi2_statistic: 'A measure of how much observed data deviates from what would be expected if there were no association.',
  log_likelihood: 'A measure of how well the model fits the data; higher (less negative) values indicate better fit.',
  aic: 'Akaike Information Criterion — balances model fit against complexity; lower is better when comparing models.',
  bic: 'Bayesian Information Criterion — similar to AIC but penalises extra parameters more; lower is better.',
  rmse: 'Root Mean Squared Error — the typical size of prediction errors, in the same units as the outcome.',
  mae: 'Mean Absolute Error — the average size of prediction errors, in the same units as the outcome.',
  dof: 'Degrees of freedom — the number of independent values that were free to vary when estimating the statistic.',
  se_type: 'The type of standard error used (e.g. classical, heteroskedasticity-robust, or cluster-robust).',
  concordance: 'The proportion of pairs where the model correctly ranks which subject experiences the event first (survival models).',
  n_factors: 'The number of latent factors extracted or specified in the model.',
  n_indicators: 'The number of observed variables used to measure the latent factor(s).',
  n_groups: 'The number of distinct groups compared in the analysis.',
  n_events: 'The number of observed events (e.g. failures, deaths) rather than censored cases.',
  event_rate: 'The proportion of subjects who experienced the event during the observation period.',
  n_subjects: 'The number of unique participants or entities in the dataset.',
  n_predictors: 'The number of predictor (independent) variables included in the model.',
  llf: 'Log-likelihood — a measure of how well the model fits the data; higher (less negative) values indicate better fit.',
  alpha: "A measure of internal consistency for a scale's items; values above 0.7 are usually considered acceptable.",
  alpha_standardized: "Cronbach's alpha computed on standardized items, useful when items have very different scales.",

  // Coefficient / summary table columns
  se: 'Standard error — the estimated variability of the coefficient; smaller means a more precise estimate.',
  t: 't-statistic — the coefficient divided by its standard error, used to test whether it differs from zero.',
  ci: 'Confidence interval — the range of plausible values for the true coefficient, typically at 95% confidence.',
  vif: 'Variance Inflation Factor — how much a predictor\'s variance is inflated due to correlation with other predictors. Above 10 usually signals a multicollinearity problem.',
  eta_sq: 'Eta-squared — the proportion of total variance in the outcome attributable to this factor.',
  effect_size: 'A standardised measure of how large an effect is, independent of sample size.',
  corrected_item_total: 'How well this item correlates with the total score of all other items — low values suggest the item doesn\'t fit the scale well.',
  alpha_if_deleted: 'What Cronbach\'s alpha would be if this item were removed from the scale. If it\'s higher than the overall alpha, removing the item may improve reliability.',
}
