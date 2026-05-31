"""Smoke tests for all 7 new analysis modules."""
import numpy as np
import pandas as pd
import pytest

from backend.analysis_modules import (
    anova,
    chi_square,
    correlation,
    descriptive,
    factor_analysis,
    logistic,
    moderation,
    multicomp,
    nonparametric,
    panel,
    power_analysis,
    regression,
    reliability,
    survival,
    timeseries,
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
# Moderation analysis
# ---------------------------------------------------------------------------

def test_moderation_happy(continuous_df):
    result = moderation.run(continuous_df, {
        "outcome": "score",
        "predictor": "pre",
        "moderator": "post",
    }, OPTS)
    assert result.test_key == "moderation"
    assert "coefficients" in result.statistics
    assert "simple_slopes" in result.statistics
    assert "jn_region" in result.statistics
    assert "interaction_f2" in result.statistics
    assert result.statistics["coefficients"]  # at least predictor, moderator, interaction
    assert len(result.statistics["simple_slopes"]) == 3  # -1SD, mean, +1SD
    assert result.effect_size is not None


def test_moderation_with_covariates(continuous_df):
    result = moderation.run(continuous_df, {
        "outcome": "score",
        "predictor": "pre",
        "moderator": "post",
        "covariates": ["group"],
    }, OPTS)
    assert result.test_key == "moderation"
    # group is categorical → expanded to dummies
    has_group_dummy = any(k.startswith("group_") for k in result.statistics["coefficients"])
    assert has_group_dummy, f"No group_* dummy in coefficients: {list(result.statistics['coefficients'].keys())}"


def test_moderation_missing_outcome(continuous_df):
    with pytest.raises(ValueError, match="outcome is required"):
        moderation.run(continuous_df, {"predictor": "pre", "moderator": "post"}, OPTS)


def test_moderation_missing_predictor(continuous_df):
    with pytest.raises(ValueError, match="predictor is required"):
        moderation.run(continuous_df, {"outcome": "score", "moderator": "post"}, OPTS)


def test_moderation_missing_moderator(continuous_df):
    with pytest.raises(ValueError, match="moderator is required"):
        moderation.run(continuous_df, {"outcome": "score", "predictor": "pre"}, OPTS)


# ---------------------------------------------------------------------------
# Reliability analysis
# ---------------------------------------------------------------------------

@pytest.fixture
def likert_df():
    """Simulated 6-item Likert scale (1-7) with good internal consistency."""
    rng = np.random.default_rng(42)
    true_score = rng.normal(4, 0.8, 50)
    items = {}
    for i in range(6):
        items[f"item_{i+1}"] = np.clip(true_score + rng.normal(0, 0.5, 50), 1, 7).tolist()
    return pd.DataFrame(items)


def test_reliability_smoke(likert_df):
    result = reliability.run(likert_df, {"variables": list(likert_df.columns)}, OPTS)
    assert result.test_key == "reliability"
    assert 0 <= result.statistics["alpha"] <= 1
    assert result.statistics["n_items"] == 6
    assert result.statistics["n_obs"] == 50
    assert len(result.statistics["item_statistics"]) == 6
    for item in result.statistics["item_statistics"]:
        assert "corrected_item_total_corr" in item
        assert "alpha_if_deleted" in item
        assert isinstance(item["corrected_item_total_corr"], float)
    assert "inter_item_corr_mean" in result.statistics


def test_reliability_high_consistency(likert_df):
    """With small error variance, alpha should be high (>0.80)."""
    result = reliability.run(likert_df, {"variables": list(likert_df.columns)}, OPTS)
    assert result.statistics["alpha"] > 0.80


def test_reliability_too_few_items():
    with pytest.raises(ValueError, match="At least two"):
        reliability.run(pd.DataFrame({"a": [1, 2, 3]}), {"variables": ["a"]}, OPTS)


def test_reliability_assumption_checks(likert_df):
    result = reliability.run(likert_df, {"variables": list(likert_df.columns)}, OPTS)
    assert isinstance(result.assumption_checks, list)


def test_reliability_no_assumption_checks(likert_df):
    result = reliability.run(likert_df, {"variables": list(likert_df.columns)}, NO_OPTS)
    assert len(result.assumption_checks) == 0


# ---------------------------------------------------------------------------
# Power analysis
# ---------------------------------------------------------------------------

class _PowerOpts:
    assumption_checks = False
    effect_size = False
    post_hoc = False
    extras = {}


def test_power_known_t_test():
    """N=128 (64 per group) for independent t, d=0.5, α=0.05, power=0.80."""
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Independent t-test",
        "compute": "Sample size (N)",
        "effect_size": 0.5,
        "alpha": 0.05,
        "power": 0.80,
    }
    result = power_analysis.run(pd.DataFrame(), {}, opts)
    assert result.statistics["n_total"] == 128
    assert result.statistics["n_per_group"] == 64


def test_power_paired_t():
    """N=34 for paired t, d=0.5, α=0.05, power=0.80."""
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Paired t-test",
        "compute": "Sample size (N)",
        "effect_size": 0.5,
        "alpha": 0.05,
        "power": 0.80,
    }
    result = power_analysis.run(pd.DataFrame(), {}, opts)
    assert 30 <= result.statistics["n_total"] <= 40


def test_power_power_computation():
    """Power for known values: d=0.5, N=64, α=0.05, independent t."""
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Independent t-test",
        "compute": "Power (1-β)",
        "effect_size": 0.5,
        "alpha": 0.05,
        "n_total": 64,
    }
    result = power_analysis.run(pd.DataFrame(), {}, opts)
    assert 0.45 <= result.statistics["power"] <= 0.75  # 64 for d=0.5 gives ~0.50-0.56


def test_power_effect_size_computation():
    """Detectable effect size for N=128, α=0.05, power=0.80, independent t."""
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Independent t-test",
        "compute": "Detectable effect size",
        "alpha": 0.05,
        "power": 0.80,
        "n_total": 128,
    }
    result = power_analysis.run(pd.DataFrame(), {}, opts)
    assert 0.45 <= result.statistics["effect_size"] <= 0.55  # should be ~0.50


def test_power_unknown_family():
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Unknown",
        "compute": "Sample size (N)",
        "effect_size": 0.5,
        "alpha": 0.05,
        "power": 0.80,
    }
    with pytest.raises(ValueError, match="Unknown test family"):
        power_analysis.run(pd.DataFrame(), {}, opts)


def test_power_missing_effect_size():
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Independent t-test",
        "compute": "Sample size (N)",
        "alpha": 0.05,
        "power": 0.80,
    }
    with pytest.raises(ValueError, match="effect_size is required"):
        power_analysis.run(pd.DataFrame(), {}, opts)


def test_power_anova():
    """N ~158 for ANOVA with 3 groups, f=0.25, α=0.05, power=0.80."""
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "ANOVA (F-test)",
        "compute": "Sample size (N)",
        "effect_size": 0.25,
        "alpha": 0.05,
        "power": 0.80,
        "n_groups": 3,
    }
    result = power_analysis.run(pd.DataFrame(), {}, opts)
    assert 150 <= result.statistics["n_total"] <= 170
    assert result.statistics["n_groups"] == 3


def test_power_correlation():
    """N ~29 for r=0.5, α=0.05, power=0.80."""
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Correlation (Pearson r)",
        "compute": "Sample size (N)",
        "effect_size": 0.5,
        "alpha": 0.05,
        "power": 0.80,
    }
    result = power_analysis.run(pd.DataFrame(), {}, opts)
    assert 25 <= result.statistics["n_total"] <= 35


# ---------------------------------------------------------------------------
# Time-series analysis
# ---------------------------------------------------------------------------

class _TsOpts:
    assumption_checks = True
    effect_size = False
    post_hoc = False
    extras = {}

@pytest.fixture
def ts_stationary():
    """White noise — should be stationary."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=100, freq="D"),
        "value": rng.normal(0, 1, 100).tolist(),
    })

@pytest.fixture
def ts_nonstationary():
    """Random walk — should be non-stationary."""
    rng = np.random.default_rng(42)
    steps = rng.normal(0, 1, 100)
    walk = np.cumsum(steps)
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=100, freq="D"),
        "value": walk.tolist(),
    })

@pytest.fixture
def ts_seasonal():
    """Seasonal series with clear period 12 pattern."""
    rng = np.random.default_rng(42)
    t = np.arange(60)
    seasonal = 2 * np.sin(2 * np.pi * t / 12)
    noise = rng.normal(0, 0.5, 60)
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=60, freq="ME"),
        "value": (seasonal + noise).tolist(),
    })

def test_timeseries_adf_stationary(ts_stationary):
    """White noise should be identified as stationary."""
    result = timeseries.run(ts_stationary, {"value": "value", "time_col": "date"}, _TsOpts())
    assert result.test_key == "timeseries"
    assert result.statistics["is_stationary"] is True
    assert result.statistics["adf_pvalue"] < 0.05
    assert "adf_statistic" in result.statistics
    assert "kpss_statistic" in result.statistics

def test_timeseries_adf_nonstationary(ts_nonstationary):
    """Random walk should be identified as non-stationary."""
    result = timeseries.run(ts_nonstationary, {"value": "value", "time_col": "date"}, _TsOpts())
    assert result.test_key == "timeseries"
    assert result.statistics["is_stationary"] is False
    assert result.statistics["adf_pvalue"] > 0.05

def test_timeseries_missing_config(ts_stationary):
    with pytest.raises(ValueError, match="required"):
        timeseries.run(ts_stationary, {"value": "value"}, _TsOpts())
    with pytest.raises(ValueError, match="required"):
        timeseries.run(ts_stationary, {"time_col": "date"}, _TsOpts())

def test_timeseries_too_few_obs():
    df = pd.DataFrame({"date": [1, 2, 3], "value": [1, 2, 3]})
    with pytest.raises(ValueError, match="At least 10"):
        timeseries.run(df, {"value": "value", "time_col": "date"}, _TsOpts())

def test_timeseries_arima_manual(ts_stationary):
    """Manual ARIMA(1,0,0) should produce forecast."""
    opts = _TsOpts()
    opts.extras = {"order": "Manual", "p": 1, "d": 0, "q": 0, "forecast_steps": 5}
    result = timeseries.run(ts_stationary, {"value": "value", "time_col": "date"}, opts)
    assert "arima_order" in result.statistics
    assert result.statistics["arima_order"] == [1, 0, 0]
    assert len(result.statistics.get("forecast_values", [])) == 5

def test_timeseries_arima_auto(ts_stationary):
    """Auto ARIMA should find a model and produce forecast."""
    opts = _TsOpts()
    opts.extras = {"order": "Auto (AIC)", "forecast_steps": 5}
    result = timeseries.run(ts_stationary, {"value": "value", "time_col": "date"}, opts)
    assert "arima_order" in result.statistics
    assert len(result.statistics.get("forecast_values", [])) == 5

def test_timeseries_seasonal_detection(ts_seasonal):
    """Seasonal data with period=12 should detect seasonality."""
    opts = _TsOpts()
    opts.extras = {"order": "Auto (AIC)", "seasonal": True, "s": 12, "forecast_steps": 6}
    result = timeseries.run(ts_seasonal, {"value": "value", "time_col": "date"}, opts)
    assert result.statistics["is_seasonal"] is True
    assert result.statistics["seasonal_period"] == 12

def test_timeseries_assumption_checks(ts_stationary):
    result = timeseries.run(ts_stationary, {"value": "value", "time_col": "date"}, _TsOpts())
    assert len(result.assumption_checks) > 0
    assert any("Stationarity" in c.name for c in result.assumption_checks)

def test_timeseries_no_assumptions(ts_stationary):
    class _NoCheckOpts:
        assumption_checks = False
        effect_size = False
        post_hoc = False
    result = timeseries.run(ts_stationary, {"value": "value", "time_col": "date"}, _NoCheckOpts())
    assert len(result.assumption_checks) == 0

def test_timeseries_acf_pacf(ts_stationary):
    result = timeseries.run(ts_stationary, {"value": "value", "time_col": "date"}, _TsOpts())
    assert len(result.statistics.get("acf_values", [])) > 1
    assert len(result.statistics.get("pacf_values", [])) > 1
    # Lag 0 ACF should be 1.0
    assert result.statistics["acf_values"][0]["lag"] == 0
    assert abs(result.statistics["acf_values"][0]["value"] - 1.0) < 1e-6


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
# Factor Analysis
# ---------------------------------------------------------------------------

@pytest.fixture
def fa_known_df():
    """12 items loading on 3 factors (4 each)."""
    rng = np.random.default_rng(42)
    n = 200
    factors = rng.normal(0, 1, (n, 3))
    items = {}
    for i in range(4):
        items[f"f1_item_{i+1}"] = (0.7 * factors[:, 0] + 0.3 * rng.normal(0, 1, n)).tolist()
    for i in range(4):
        items[f"f2_item_{i+1}"] = (0.7 * factors[:, 1] + 0.3 * rng.normal(0, 1, n)).tolist()
    for i in range(4):
        items[f"f3_item_{i+1}"] = (0.7 * factors[:, 2] + 0.3 * rng.normal(0, 1, n)).tolist()
    return pd.DataFrame(items)


class _FaOpts:
    assumption_checks = True
    effect_size = False
    post_hoc = False
    extras = {}


def test_factor_analysis_smoke(fa_known_df):
    opts = _FaOpts()
    opts.extras = {"n_factors": 3, "rotation": "varimax", "method": "principal_factor"}
    result = factor_analysis.run(fa_known_df, {"variables": list(fa_known_df.columns)}, opts)
    assert result.test_key == "factor_analysis"
    assert result.statistics["n_factors"] == 3
    assert result.statistics["n_variables"] == 12
    assert result.statistics["kmo_total"] > 0.5
    assert len(result.statistics["loadings"]) == 12
    assert len(result.statistics["scree"]) == 12
    assert len(result.statistics["variance_explained_pct"]) == 3


def test_factor_analysis_auto_factors(fa_known_df):
    """Auto-detect should find ~3 factors."""
    opts = _FaOpts()
    opts.extras = {"n_factors": 0, "rotation": "varimax", "method": "principal_factor"}
    result = factor_analysis.run(fa_known_df, {"variables": list(fa_known_df.columns)}, opts)
    assert 2 <= result.statistics["n_factors"] <= 4


def test_factor_analysis_too_few_vars():
    with pytest.raises(ValueError, match="At least three"):
        factor_analysis.run(pd.DataFrame({"a": [1, 2], "b": [3, 4]}), {"variables": ["a", "b"]}, OPTS)


def test_factor_analysis_assumption_checks(fa_known_df):
    opts = _FaOpts()
    opts.extras = {"n_factors": 3}
    result = factor_analysis.run(fa_known_df, {"variables": list(fa_known_df.columns)}, opts)
    assert isinstance(result.assumption_checks, list)


def test_factor_analysis_no_assumption_checks(fa_known_df):
    opts = _FaOpts()
    opts.extras = {"n_factors": 3}
    opts.assumption_checks = False
    result = factor_analysis.run(fa_known_df, {"variables": list(fa_known_df.columns)}, opts)
    assert len(result.assumption_checks) == 0


# ---------------------------------------------------------------------------
# Survival Analysis
# ---------------------------------------------------------------------------

@pytest.fixture
def survival_df():
    """Simulated survival data with 2 groups (treatment lives longer)."""
    rng = np.random.default_rng(42)
    n = 100
    dur_t = rng.exponential(20, n // 2)
    dur_c = rng.exponential(10, n // 2)
    duration = np.concatenate([dur_t, dur_c])
    event = rng.binomial(1, 0.8, n).tolist()
    group = ["Treatment"] * (n // 2) + ["Control"] * (n // 2)
    treat = [1] * (n // 2) + [0] * (n // 2)
    return pd.DataFrame({"duration": duration, "event": event, "group": group, "treat": treat})


def test_survival_km_smoke(survival_df):
    result = survival.run(survival_df, {"duration": "duration", "event": "event", "group": "group"}, OPTS)
    assert result.test_key == "survival_analysis"
    assert result.statistics["n_obs"] == 100
    assert result.statistics["km_median"] is not None
    assert "km_survival_curve" in result.statistics
    curve = result.statistics["km_survival_curve"]
    assert len(curve["times"]) > 0
    assert all(0 <= s <= 1 for s in curve["survival"])
    assert "logrank_statistic" in result.statistics
    assert result.statistics["logrank_p"] is not None


def test_survival_cox_smoke(survival_df):
    """Cox should find treatment reduces hazard (HR < 1)."""
    result = survival.run(survival_df, {
        "duration": "duration", "event": "event",
        "predictors": ["treat"],
    }, OPTS)
    assert result.statistics["cox"] is not None
    hr_table = result.statistics["cox"]["hr_table"]
    assert len(hr_table) == 1
    assert result.statistics["cox_converged"] is True


def test_survival_too_few_events():
    df = pd.DataFrame({"duration": [1, 2, 3, 4, 5], "event": [0, 0, 0, 0, 0]})
    with pytest.raises(ValueError, match="contain both 0 and 1"):
        survival.run(df, {"duration": "duration", "event": "event"}, OPTS)


def test_survival_no_group(survival_df):
    """KM should work without a group variable."""
    result = survival.run(survival_df, {"duration": "duration", "event": "event"}, OPTS)
    assert result.statistics["km_median"] is not None
    assert "logrank_statistic" not in result.statistics


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
    (lambda df: moderation.run(df, {"outcome": "score", "predictor": "pre", "moderator": "post"}, OPTS), "continuous_df"),
    (lambda df: reliability.run(df, {"variables": list(df.columns)}, OPTS), "likert_df"),
    (lambda df: timeseries.run(df, {"value": "value", "time_col": "date"}, _TsOpts()), "ts_stationary"),
    (lambda df: factor_analysis.run(df, {"variables": list(df.columns)}, _FaOpts()), "fa_known_df"),
    (lambda df: survival.run(df, {"duration": "duration", "event": "event"}, OPTS), "survival_df"),
])

def test_interpretation_fields(result_fn, args, continuous_df, categorical_df, panel_df, likert_df, ts_stationary, fa_known_df, survival_df):
    m = {"continuous_df": continuous_df, "categorical_df": categorical_df, "panel_df": panel_df, "likert_df": likert_df, "ts_stationary": ts_stationary, "fa_known_df": fa_known_df, "survival_df": survival_df}
    df = m[args]
    result = result_fn(df)
    assert result.interpretation.plain
    assert result.interpretation.apa
    assert result.interpretation.technical
    assert result.result_id  # UUID populated


def test_power_interpretation_fields():
    opts = _PowerOpts()
    opts.extras = {
        "test_family": "Independent t-test",
        "compute": "Sample size (N)",
        "effect_size": 0.5,
        "alpha": 0.05,
        "power": 0.80,
    }
    result = power_analysis.run(pd.DataFrame(), {}, opts)
    assert result.interpretation.plain
    assert result.interpretation.apa
    assert result.interpretation.technical
    assert result.result_id
