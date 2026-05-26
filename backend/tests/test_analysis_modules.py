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
    nonparametric,
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
    if result.statistics["post_hoc"]:
        assert "group1" in result.statistics["post_hoc"][0]


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
# Correlation
# ---------------------------------------------------------------------------

def test_correlation_happy(continuous_df):
    result = correlation.run(continuous_df, {"col_a": "pre", "col_b": "post"}, OPTS)
    assert result.test_key == "correlation"
    assert "pearson" in result.statistics
    assert "spearman" in result.statistics
    assert "kendall" in result.statistics


def test_correlation_missing_config(continuous_df):
    with pytest.raises(ValueError, match="required"):
        correlation.run(continuous_df, {"col_a": "pre"}, OPTS)


def test_correlation_too_few_obs():
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    with pytest.raises(ValueError, match="At least 3"):
        correlation.run(df, {"col_a": "a", "col_b": "b"}, OPTS)


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
    (lambda df: correlation.run(df, {"col_a": "pre", "col_b": "post"}, OPTS), "continuous_df"),
])
def test_interpretation_fields(result_fn, args, continuous_df, categorical_df):
    df = continuous_df if args == "continuous_df" else categorical_df
    result = result_fn(df)
    assert result.interpretation.plain
    assert result.interpretation.apa
    assert result.interpretation.technical
    assert result.result_id  # UUID populated
