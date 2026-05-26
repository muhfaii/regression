from typing import Optional

# Mirror of frontend/src/constants/wizard.ts ROUTING_TABLE.
# Each entry: (q1, q2, q3, q4) -> (test_key, reason)
# None = wildcard ("I'm not sure")

_ROUTING_TABLE: list[tuple[tuple, str, str]] = [
    (('compare', '2', 'continuous', 'yes'), 'independent_t', "You want to compare the means of two groups on a continuous, normally distributed outcome."),
    (('compare', '2', 'continuous', 'no'),  'mann_whitney',  "Your outcome is continuous but not normally distributed, so a non-parametric test is more appropriate."),
    (('compare', '2', 'continuous', None),  'independent_t', "You want to compare two groups on a continuous outcome."),
    (('compare', '3+', 'continuous', 'yes'), 'one_way_anova', "You have three or more groups and a continuous, normally distributed outcome — ANOVA is the right choice."),
    (('compare', '3+', 'continuous', 'no'),  'kruskal_wallis', "You have three or more groups but your data is not normally distributed, so a non-parametric alternative is better."),
    (('compare', '3+', 'continuous', None),  'one_way_anova', "You want to compare three or more groups on a continuous outcome."),
    (('compare', '2',  'categorical', None), 'chi_square', "Your outcome is categorical, so chi-square tests the association between the group and the outcome."),
    (('compare', '3+', 'categorical', None), 'chi_square', "Your outcome is categorical, so chi-square tests the association between the group and the outcome."),
    (('compare', 'paired', 'continuous', 'yes'), 'paired_t',  "You are comparing paired measurements and your data is normally distributed."),
    (('compare', 'paired', 'continuous', 'no'),  'wilcoxon',  "You are comparing paired measurements but your data is not normally distributed."),
    (('compare', 'paired', 'continuous', None),  'paired_t',  "You are comparing paired measurements on a continuous outcome."),
    (('describe', None, None, None), 'descriptive',        "You want to summarise your data — descriptive statistics will give you means, variability, and distribution shape."),
    (('relate', None, 'continuous',  None), 'correlation',  "You want to measure the relationship between two continuous variables."),
    (('relate', None, 'categorical', None), 'chi_square',   "You want to test the association between two categorical variables."),
    (('relate', None, None, None),           'correlation',  "You want to explore the relationship between two variables."),
    (('predict', None, 'continuous',  None), 'ols_regression',     "You want to predict a continuous outcome from one or more variables — OLS regression is the standard approach."),
    (('predict', None, 'categorical', None), 'logistic_regression', "You want to predict a categorical (binary) outcome — logistic regression models the probability of each class."),
    (('predict', None, None, None),          'ols_regression',     "You want to predict an outcome from other variables."),
    ((None, None, None, None), 'descriptive', "Start with descriptive statistics to explore your data before choosing an inferential test."),
]

WizardAnswers = tuple[Optional[str], Optional[str], Optional[str], Optional[str]]


def resolve_test(answers: WizardAnswers) -> dict:
    # Exact match first
    for pattern, test_key, reason in _ROUTING_TABLE:
        if all(p == a for p, a in zip(pattern, answers)):
            return {"test_key": test_key, "reason": reason}
    # Wildcard match: None in pattern matches anything
    for pattern, test_key, reason in _ROUTING_TABLE:
        if all(p is None or p == a for p, a in zip(pattern, answers)):
            return {"test_key": test_key, "reason": reason}
    return {"test_key": "descriptive", "reason": "Start with descriptive statistics to explore your data."}
