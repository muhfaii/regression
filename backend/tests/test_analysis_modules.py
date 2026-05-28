"""Smoke tests for all 7 new analysis modules."""
import numpy as np
import pandas as pd
import pytest

from backend.analysis_modules import (
    anova,
    chi_square,
    correlation,
    descriptive,
    logistic,
    multicomp,
    nonparametric,
    panel,
    regression,
    t_tests,
)
from backend.schemas.analysis import AnalysisOptions


class _Opts:
    """Minimal options object matching AnalysisOptions defaults."""
    assumption_checks = True
    effect_size = True
    post_hoc = True


OPTS = _Opts()
NO_OPTS = type("NoOpts", (), {"assumption_checks": False, "effect_size": False, "post_hoc": False})()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def continuous_df():
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "score": rng.normal(50, 10, 60).tolist(),
        "group": (["A"] * 20 + ["B"] * 20 + ["C"] * 20),
        "group2": (["X"] * 30 + ["Y"] * 30),
        "pre": rng.normal(40, 8, 60).tolist(),
        "post": rng.normal(45, 8, 60).tolist(),
    })


@pytest.fixture
def panel_df():
    rng = np.random.default_rng(42)
    entities = ["A", "B", "C", "D"]
    years = [2010, 2011, 2012, 2013]
    rows = []
    for e in entities:
        for y in years:
            rows.append({
                "entity_id": e,
                "year": y,
                "y": rng.normal(0, 1),
                "x1": rng.normal(5, 2),
                "x2": rng.normal(10, 3),
            })
    return pd.DataFrame(rows)


@pytest.fixture
def categorical_df():
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "gender": rng.choice(["M", "F"], 80).tolist(),
        "outcome": rng.choice(["pass", "fail"], 80).tolist(),
        "edu": rng.choice(["high", "medium", "low"], 80).tolist(),
        "income": rng.normal(50000, 10000, 80).tolist(),
    })


# ---------------------------------------------------------------------------
# Descriptive
# ---------------------------------------------------------------------------

def test_descriptive_single(continuous_df):
    result = descriptive.run(continuous_df, {"variables": ["score"]}, OPTS)
    assert result.test_key == "descriptive"
    assert "score" in result.statistics["variables"]
    s = result.statistics["variables"]["score"]
    assert "mean" in s and "sd" in s and "skewness" in s


def test_descriptive_multiple(continuous_df):
    result = descriptive.run(continuous_df, {"variables": ["score", "pre", "post"]}, OPTS)
    assert set(result.statistics["variables"].keys()) == {"score", "pre", "post"}


def test_descriptive_missing_vars():
    with pytest.raises(ValueError, match="At least one variable"):
        descriptive.run(pd.DataFrame({"x": [1, 2]}), {}, OPTS)


# ---------------------------------------------------------------------------
# T-tests
# ---------------------------------------------------------------------------

def test_independent_t_happy(continuous_df):
    result = t_tests.run_independent_t(continuous_df, {"outcome": "score", "group": "group2"}, OPTS)
    assert result.test_key == "independent_t"
    assert "t_statistic" in result.statistics
    assert "p_value" in result.statistics
    assert result.effect_size is not None


def test_independent_t_wrong_group_count(continuous_df):
    with pytest.raises(ValueError, match="exactly 2 groups"):
        t_tests.run_independent_t(continuous_df, {"outcome": "score", "group": "group"}, OPTS)


def test_independent_t_missing_config(continuous_df):
    with pytest.raises(ValueError, match="required"):
        t_tests.run_independent_t(continuous_df, {"outcome": "score"}, OPTS)


def test_paired_t_happy(continuous_df):
    result = t_tests.run_paired_t(continuous_df, {"col_a": "pre", "col_b": "post"}, OPTS)
    assert result.test_key == "paired_t"
    assert "mean_diff" in result.statistics
    assert result.effect_size is not None


def test_paired_t_missing_config(continuous_df):
    with pytest.raises(ValueError, match="required"):
        t_tests.run_paired_t(continuous_df, {"col_a": "pre"}, OPTS)


# ---------------------------------------------------------------------------
# ANOVA
# ---------------------------------------------------------------------------

def test_anova_happy(continuous_df):
    result = anova.run(continuous_df, {"outcome": "score", "group": "group"}, OPTS)
    assert result.test_key == "one_way_anova"
    assert "f_statistic" in result.statistics
    assert result.effect_size is not None


def test_anova_post_hoc(continuous_df):
    result = anova.run(continuous_df, {"outcome": "score", "group": "group"}, OPTS)
    # Post-hoc is only populated when p < 0.05; check structure if present
    ph = result.statistics.get("post_hoc")
    if ph:
        assert "group1" in ph[0]


def test_anova_too_few_groups(continuous_df):
    with pytest.raises(ValueError, match="at least 3 groups"):
        anova.run(continuous_df, {"outcome": "score", "group": "group2"}, OPTS)


# ---------------------------------------------------------------------------
# Non-parametric
# ---------------------------------------------------------------------------

def test_mann_whitney_happy(continuous_df):
    result = nonparametric.run_mann_whitney(continuous_df, {"outcome": "score", "group": "group2"}, OPTS)
    assert result.test_key == "mann_whitney"
    assert "u_statistic" in result.statistics


def test_mann_whitney_wrong_groups(continuous_df):
    with pytest.raises(ValueError, match="exactly 2 groups"):
        nonparametric.run_mann_whitney(continuous_df, {"outcome": "score", "group": "group"}, OPTS)


def test_wilcoxon_happy(continuous_df):
    result = nonparametric.run_wilcoxon(continuous_df, {"col_a": "pre", "col_b": "post"}, OPTS)
    assert result.test_key == "wilcoxon"
    assert "w_statistic" in result.statistics


def test_kruskal_wallis_happy(continuous_df):
    result = nonparametric.run_kruskal_wallis(continuous_df, {"outcome": "score", "group": "group"}, OPTS)
    assert result.test_key == "kruskal_wallis"
    assert "h_statistic" in result.statistics


def test_kruskal_wallis_too_few_groups(continuous_df):
    with pytest.raises(ValueError, match="at least 3 groups"):
        nonparametric.run_kruskal_wallis(continuous_df, {"outcome": "score", "group": "group2"}, OPTS)


# ---------------------------------------------------------------------------
# Correlation (matrix)
# ---------------------------------------------------------------------------

def test_correlation_happy(continuous_df):
    result = correlation.run(continuous_df, {"variables": ["pre", "post"]}, OPTS)
    assert result.test_key == "correlation"
    assert "matrix_pearson" in result.statistics
    assert "matrix_spearman" in result.statistics
    assert "matrix_kendall" in result.statistics
    assert result.statistics["n_vars"] == 2


def test_correlation_multi_vars(continuous_df):
    result = correlation.run(continuous_df, {"variables": ["score", "pre", "post"]}, OPTS)
    assert result.statistics["n_vars"] == 3
    assert len(result.statistics["matrix_pearson"]) == 3


def test_correlation_missing_config(continuous_df):
    with pytest.raises(ValueError, match="At least two variables"):
        correlation.run(continuous_df, {"variables": ["score"]}, OPTS)


def test_correlation_too_few_obs():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    with pytest.raises(ValueError, match="At least 3"):
        correlation.run(df, {"variables": ["a", "b"]}, OPTS)


# ---------------------------------------------------------------------------
# Factorial ANOVA
# ---------------------------------------------------------------------------

def test_factorial_anova_happy(continuous_df):
    result = anova.run_factorial(continuous_df, {"outcome": "score", "factors": ["group", "group2"]}, OPTS)
    assert result.test_key == "factorial_anova"
    assert "terms" in result.statistics
    assert len(result.statistics["terms"]) >= 2


def test_factorial_anova_too_few_factors(continuous_df):
    with pytest.raises(ValueError, match="at least two factors"):
        anova.run_factorial(continuous_df, {"outcome": "score", "factors": ["group"]}, OPTS)


def test_factorial_anova_missing_config(continuous_df):
    with pytest.raises(ValueError, match="required"):
        anova.run_factorial(continuous_df, {"outcome": "score"}, OPTS)


# ---------------------------------------------------------------------------
# Chi-square
# ---------------------------------------------------------------------------

def test_chi_square_happy(categorical_df):
    result = chi_square.run(categorical_df, {"col_a": "gender", "col_b": "outcome"}, OPTS)
    assert result.test_key == "chi_square"
    assert "chi2" in result.statistics
    assert "cramers_v" in result.statistics


def test_chi_square_missing_config(categorical_df):
    with pytest.raises(ValueError, match="required"):
        chi_square.run(categorical_df, {"col_a": "gender"}, OPTS)


# ---------------------------------------------------------------------------
# Panel regression
# ---------------------------------------------------------------------------

def test_panel_regression_happy(panel_df):
    result = panel.run(panel_df, {
        "dep_var": "y",
        "indep_vars": ["x1", "x2"],
        "entity_col": "entity_id",
        "time_col": "year",
    }, OPTS)
    assert result.test_key == "panel_regression"
    assert result.statistics["model_type"] in ("fe", "re", "pooled_ols")
    assert "r_squared" in result.statistics
    assert "bplm" in result.statistics
    assert "hausman" in result.statistics
    assert len(result.statistics["coefficients"]) > 0
    assert result.statistics["selection_steps"]


def test_panel_missing_entity_col(panel_df):
    with pytest.raises(ValueError, match="entity_col is required"):
        panel.run(panel_df, {
            "dep_var": "y",
            "indep_vars": ["x1"],
            "time_col": "year",
        }, OPTS)


def test_panel_missing_time_col(panel_df):
    with pytest.raises(ValueError, match="time_col is required"):
        panel.run(panel_df, {
            "dep_var": "y",
            "indep_vars": ["x1"],
            "entity_col": "entity_id",
        }, OPTS)


def test_panel_se_override(panel_df):
    class _SeOpts:
        assumption_checks = True
        effect_size = True
        post_hoc = False
        se_type = "CR1"
    result = panel.run(panel_df, {
        "dep_var": "y",
        "indep_vars": ["x1", "x2"],
        "entity_col": "entity_id",
        "time_col": "year",
    }, _SeOpts())
    assert isinstance(result.statistics["se_type"], str)
    assert result.statistics["se_type"]


# ---------------------------------------------------------------------------
# Logistic regression
# ---------------------------------------------------------------------------

def test_logistic_happy(categorical_df):
    result = logistic.run(categorical_df, {"outcome": "outcome", "predictors": ["income"]}, OPTS)
    assert result.test_key == "logistic_regression"
    assert "nagelkerke_r2" in result.statistics
    assert "coefficients" in result.statistics


def test_logistic_non_binary(continuous_df):
    with pytest.raises(ValueError, match="binary outcome"):
        logistic.run(continuous_df, {"outcome": "group", "predictors": ["score"]}, OPTS)


def test_logistic_missing_config(categorical_df):
    with pytest.raises(ValueError, match="required"):
        logistic.run(categorical_df, {"outcome": "outcome"}, OPTS)


# ---------------------------------------------------------------------------
# Multiple comparison corrections
# ---------------------------------------------------------------------------

def test_multicomp_basic():
    p = [0.001, 0.012, 0.038, 0.21, 0.50]
    adj = multicomp.adjust_pvalues(p, "bonferroni")
    assert len(adj) == 5
    assert adj[0] <= 0.01  # 0.001 * 5 = 0.005
    assert all(a >= p[i] for i, a in enumerate(adj))  # adjusted >= raw


def test_multicomp_fdr_bh():
    p = [0.001, 0.012, 0.038, 0.21, 0.50]
    adj = multicomp.adjust_pvalues(p, "fdr_bh")
    assert len(adj) == 5
    assert all(a >= p[i] for i, a in enumerate(adj))


def test_multicomp_empty():
    adj = multicomp.adjust_pvalues([], "bonferroni")
    assert len(adj) == 0


def test_multicomp_invalid_method():
    with pytest.raises(ValueError, match="Unknown correction method"):
        multicomp.adjust_pvalues([0.05], "invalid")


# ---------------------------------------------------------------------------
# Correlation with p-value adjustment
# ---------------------------------------------------------------------------

def test_correlation_p_adjust(continuous_df):
    class _AdjOpts:
        assumption_checks = True
        effect_size = True
        post_hoc = False
        p_adjust = "fdr_bh"
    result = correlation.run(continuous_df, {"variables": ["score", "pre", "post"]}, _AdjOpts())
    assert "p_adjust_method" in result.statistics
    assert result.statistics["p_adjust_method"] == "fdr_bh"
    assert "matrix_p_pearson_adj" in result.statistics
    assert "matrix_p_spearman_adj" in result.statistics
    assert "matrix_p_kendall_adj" in result.statistics
    # Adjusted p-values should be >= raw p-values
    raw = result.statistics["matrix_p_pearson"]
    adj = result.statistics["matrix_p_pearson_adj"]
    for i in range(len(raw)):
        for j in range(len(raw)):
            assert adj[i][j] >= raw[i][j] - 1e-10  # floating point tolerance


# ---------------------------------------------------------------------------
# Regression with p-value adjustment
# ---------------------------------------------------------------------------

def test_regression_p_adjust(continuous_df):
    class _AdjOpts:
        assumption_checks = True
        effect_size = True
        post_hoc = False
        se_type = "auto"
        p_adjust = "bonferroni"
    result = regression.run_ols(continuous_df, "score", ["pre", "post"], options=_AdjOpts())
    assert "p_adjust_method" in result.statistics
    assert result.statistics["p_adjust_method"] == "bonferroni"
    coefs = result.statistics["coefficients"]
    for var, c in coefs.items():
        assert "p_adjusted" in c
        assert c["p_adjusted"] >= c["p"] - 1e-10


def test_regression_no_p_adjust(continuous_df):
    class _NoAdjOpts:
        assumption_checks = True
        effect_size = True
        post_hoc = False
        se_type = "auto"
        p_adjust = "none"
    result = regression.run_ols(continuous_df, "score", ["pre", "post"], options=_NoAdjOpts())
    assert "p_adjust_method" not in result.statistics
    coefs = result.statistics["coefficients"]
    for var, c in coefs.items():
        assert "p_adjusted" not in c


# ---------------------------------------------------------------------------
# Interpretation fields present on all modules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("result_fn,args", [
    (lambda df: descriptive.run(df, {"variables": ["score"]}, OPTS), "continuous_df"),
    (lambda df: t_tests.run_independent_t(df, {"outcome": "score", "group": "group2"}, OPTS), "continuous_df"),
    (lambda df: t_tests.run_paired_t(df, {"col_a": "pre", "col_b": "post"}, OPTS), "continuous_df"),
    (lambda df: anova.run(df, {"outcome": "score", "group": "group"}, OPTS), "continuous_df"),
    (lambda df: nonparametric.run_mann_whitney(df, {"outcome": "score", "group": "group2"}, OPTS), "continuous_df"),
    (lambda df: nonparametric.run_wilcoxon(df, {"col_a": "pre", "col_b": "post"}, OPTS), "continuous_df"),
    (lambda df: nonparametric.run_kruskal_wallis(df, {"outcome": "score", "group": "group"}, OPTS), "continuous_df"),
    (lambda df: correlation.run(df, {"variables": ["pre", "post"]}, OPTS), "continuous_df"),
    (lambda df: anova.run_factorial(df, {"outcome": "score", "factors": ["group", "group2"]}, OPTS), "continuous_df"),
    (lambda df: panel.run(df, {"dep_var": "y", "indep_vars": ["x1", "x2"], "entity_col": "entity_id", "time_col": "year"}, OPTS), "panel_df"),
])
def test_interpretation_fields(result_fn, args, continuous_df, categorical_df, panel_df):
    m = {"continuous_df": continuous_df, "categorical_df": categorical_df, "panel_df": panel_df}
    df = m[args]
    result = result_fn(df)
    assert result.interpretation.plain
    assert result.interpretation.apa
    assert result.interpretation.technical
    assert result.result_id  # UUID populated
