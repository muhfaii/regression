"""
Estimation layer — wraps statsmodels (OLS) and linearmodels (FE, RE).

All estimators return a FittedModel so the diagnostic engine stays
model-type-agnostic.  Panel test helpers (BP-LM, Hausman) also live here.

Covers: FR-4.1 (cross-sectional OLS), FR-4.2 (panel FE/RE).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2 as _chi2


@dataclass
class FittedModel:
    """Model-type-agnostic container for a fitted regression.

    The diagnostic engine reads only from this object, never from
    the underlying statsmodels result directly.
    """
    model_type: str          # "ols" | "fe" | "re"  (fe/re added in Phase 2)
    dep_var: str
    indep_vars: list[str]    # excludes the constant
    n_obs: int
    n_params: int            # including the constant

    # --- coefficient table (index = variable names incl. "const") ----------
    params: pd.Series        # point estimates
    bse: pd.Series           # standard errors
    tvalues: pd.Series       # t-statistics
    pvalues: pd.Series       # p-values
    conf_int: pd.DataFrame   # columns "lower_95", "upper_95"

    # --- model fit ---------------------------------------------------------
    rsquared: float
    rsquared_adj: float
    fvalue: float
    f_pvalue: float

    # --- residuals / fitted (used by BP, White, RESET, JB) ----------------
    residuals: pd.Series     # OLS residuals, index aligned to df rows used
    fitted: pd.Series        # ŷ, same index

    # --- design matrix (used by VIF, White) --------------------------------
    X: pd.DataFrame          # includes const column, same index as residuals
    y: pd.Series             # dependent variable, same index

    # --- raw result (needed by a handful of statsmodels-native test calls) -
    _result: Any             # statsmodels RegressionResultsWrapper

    # --- FE-specific: variables dropped by drop_absorbed=True ---------------
    absorbed_vars: list[str] = None   # populated by estimate_fe when vars are dropped

    def __post_init__(self):
        if self.absorbed_vars is None:
            self.absorbed_vars = []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def estimate_ols(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
) -> FittedModel:
    """Fit OLS and return a FittedModel.

    A constant is always added (statsmodels convention: add_constant).
    Rows with any NaN in the selected columns are dropped with a warning;
    callers should apply a missing-data strategy first (regassist.ingest).

    Args:
        df:          DataFrame (post missing-data strategy).
        dep_var:     Name of the dependent variable column.
        indep_vars:  Names of the independent variable columns.

    Returns:
        FittedModel populated with all fields needed by the diagnostic engine.

    Raises:
        ValueError: If estimation fails (singular matrix, insufficient obs, etc.).
    """
    cols = [dep_var] + list(indep_vars)
    data = df[cols].dropna()

    if len(data) < len(indep_vars) + 2:
        raise ValueError(
            f"Too few complete observations ({len(data)}) to estimate a model "
            f"with {len(indep_vars)} predictor(s). Need at least {len(indep_vars) + 2}."
        )

    y = data[dep_var]
    X_raw = data[indep_vars]
    X = sm.add_constant(X_raw, has_constant="raise")  # always adds "const"

    try:
        result = sm.OLS(y, X).fit()
    except Exception as exc:
        raise ValueError(f"OLS estimation failed: {exc}") from exc

    ci = result.conf_int()
    ci.columns = ["lower_95", "upper_95"]

    return FittedModel(
        model_type="ols",
        dep_var=dep_var,
        indep_vars=list(indep_vars),
        n_obs=int(result.nobs),
        n_params=int(result.df_model + 1),  # regressors + constant
        params=result.params,
        bse=result.bse,
        tvalues=result.tvalues,
        pvalues=result.pvalues,
        conf_int=ci,
        rsquared=float(result.rsquared),
        rsquared_adj=float(result.rsquared_adj),
        fvalue=float(result.fvalue),
        f_pvalue=float(result.f_pvalue),
        residuals=result.resid,
        fitted=result.fittedvalues,
        X=X,
        y=y,
        _result=result,
    )


# ---------------------------------------------------------------------------
# Panel estimation helpers
# ---------------------------------------------------------------------------

def _prep_panel(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    entity_col: str,
    time_col: str,
) -> tuple[pd.Series, pd.DataFrame]:
    """Select columns, drop NaN rows, return (y, X) with (entity, time) MultiIndex.

    X does NOT include a constant — callers add it when needed.
    Entity/time columns are stripped from indep_vars if the user accidentally
    included them, which would otherwise cause duplicate-column errors.
    """
    # Strip entity/time from regressors — they can't be regressors in a panel model
    _indep = [v for v in indep_vars if v not in (entity_col, time_col, dep_var)]
    if not _indep:
        raise ValueError(
            "No valid independent variables remain after excluding the entity column "
            f"({entity_col!r}), time column ({time_col!r}), and dependent variable "
            f"({dep_var!r}). Please select at least one regressor that is none of these."
        )
    # Build a deduplicated column list so df[cols] never returns duplicate columns
    cols = list(dict.fromkeys([entity_col, time_col, dep_var] + _indep))
    data = df[cols].dropna().set_index([entity_col, time_col])
    y = data[dep_var]
    X = data[_indep]
    return y, X


def _lm_conf_int(result) -> pd.DataFrame:
    """Rename linearmodels conf_int() columns to ['lower_95', 'upper_95']."""
    ci = result.conf_int().copy()
    ci.columns = ["lower_95", "upper_95"]
    return ci


def _select_full_rank_cols(X: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Drop the minimum number of columns needed to make X full column rank.

    Uses QR decomposition with column pivoting.  The first `rank` pivot indices
    identify linearly independent columns; the rest are dropped.  Original column
    order is preserved among the kept columns.

    Returns:
        (X_full_rank, dropped_cols)
    """
    from scipy.linalg import qr as _qr

    vals  = X.values.astype(float)
    n_col = vals.shape[1]
    rank  = int(np.linalg.matrix_rank(vals))

    if rank == n_col:          # already full rank — nothing to do
        return X, []

    _, _, piv = _qr(vals, pivoting=True)
    keep_set  = set(piv[:rank].tolist())
    keep_cols = [X.columns[i] for i in range(n_col) if i in keep_set]
    dropped   = [X.columns[i] for i in range(n_col) if i not in keep_set]
    return X[keep_cols], dropped


# ---------------------------------------------------------------------------
# Panel point estimators
# ---------------------------------------------------------------------------

def estimate_fe(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    entity_col: str,
    time_col: str,
) -> FittedModel:
    """Fit a within (fixed-effects) panel model via linearmodels PanelOLS.

    Entity effects absorb the intercept; no constant is added.

    Args:
        df:          DataFrame (post missing-data strategy).
        dep_var:     Dependent variable column name.
        indep_vars:  Independent variable column names (no entity/time cols).
        entity_col:  Column identifying entities.
        time_col:    Column identifying time periods.

    Returns:
        FittedModel with model_type="fe".

    Raises:
        ValueError: If estimation fails.
    """
    from linearmodels.panel import PanelOLS

    y, X = _prep_panel(df, dep_var, indep_vars, entity_col, time_col)

    n_obs = len(y)
    n_entities = y.index.get_level_values(0).nunique()
    min_required = len(indep_vars) + n_entities + 1
    if n_obs < min_required:
        raise ValueError(
            f"Too few observations ({n_obs}) for FE with {n_entities} entities "
            f"and {len(indep_vars)} regressor(s)."
        )

    try:
        res = PanelOLS(y, X, entity_effects=True, drop_absorbed=True).fit(
            cov_type="unadjusted"
        )
    except Exception as exc:
        raise ValueError(f"Fixed-effects estimation failed: {exc}") from exc

    # Detect which variables were dropped (time-invariant → absorbed by entity FE)
    estimated_vars = list(res.params.index)
    absorbed = [v for v in X.columns if v not in estimated_vars]
    X_used = X[estimated_vars]   # align X to what was actually estimated

    return FittedModel(
        model_type="fe",
        dep_var=dep_var,
        indep_vars=estimated_vars,
        n_obs=int(res.nobs),
        n_params=len(estimated_vars),
        params=res.params,
        bse=res.std_errors,
        tvalues=res.tstats,
        pvalues=res.pvalues,
        conf_int=_lm_conf_int(res),
        rsquared=float(res.rsquared),
        rsquared_adj=float(res.rsquared),
        fvalue=float(res.f_statistic.stat),
        f_pvalue=float(res.f_statistic.pval),
        residuals=res.resids,
        fitted=res.fitted_values,
        X=X_used,
        y=y,
        _result=res,
        absorbed_vars=absorbed,
    )


def estimate_re(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    entity_col: str,
    time_col: str,
) -> FittedModel:
    """Fit a random-effects panel model via linearmodels RandomEffects.

    A constant column is added to X before passing to RandomEffects.

    Args:
        df:          DataFrame (post missing-data strategy).
        dep_var:     Dependent variable column name.
        indep_vars:  Independent variable column names (no entity/time cols).
        entity_col:  Column identifying entities.
        time_col:    Column identifying time periods.

    Returns:
        FittedModel with model_type="re".

    Raises:
        ValueError: If estimation fails.
    """
    from linearmodels.panel import RandomEffects

    y, X = _prep_panel(df, dep_var, indep_vars, entity_col, time_col)

    # Add constant as first column (linearmodels accepts it as a plain column)
    X_c = X.copy()
    X_c.insert(0, "const", 1.0)

    # Drop columns that would make X rank-deficient (e.g. dummy variable trap).
    # This mirrors drop_absorbed=True for FE.
    X_c, rank_dropped = _select_full_rank_cols(X_c)

    # The estimated indep_vars are those that survived rank selection (excl. const)
    estimated_vars = [v for v in X_c.columns if v != "const"]

    try:
        res = RandomEffects(y, X_c).fit(cov_type="unadjusted")
    except Exception as exc:
        raise ValueError(f"Random-effects estimation failed: {exc}") from exc

    return FittedModel(
        model_type="re",
        dep_var=dep_var,
        indep_vars=estimated_vars,
        n_obs=int(res.nobs),
        n_params=len(estimated_vars) + 1,   # regressors + constant
        params=res.params,
        bse=res.std_errors,
        tvalues=res.tstats,
        pvalues=res.pvalues,
        conf_int=_lm_conf_int(res),
        rsquared=float(res.rsquared),
        rsquared_adj=float(res.rsquared),
        fvalue=float(res.f_statistic.stat),
        f_pvalue=float(res.f_statistic.pval),
        residuals=res.resids,
        fitted=res.fitted_values,
        X=X_c,
        y=y,
        _result=res,
        absorbed_vars=rank_dropped,
    )


# ---------------------------------------------------------------------------
# Panel specification tests
# ---------------------------------------------------------------------------

@dataclass
class BPLMResult:
    """Breusch-Pagan Lagrange Multiplier test result (pooled OLS vs RE)."""
    statistic: float
    p_value: float
    verdict: str    # "re_preferred" | "pooled_ok"
    note: str


def bp_lm_test(
    df: pd.DataFrame,
    dep_var: str,
    indep_vars: list[str],
    entity_col: str,
    time_col: str,
) -> BPLMResult:
    """Breusch-Pagan LM test for random individual effects.

    H₀: σ²_u = 0  — no individual effects; pooled OLS is consistent.
    H₁: σ²_u > 0  — random effects present; RE is preferred to pooled OLS.

    The LM statistic is computed from pooled-OLS residuals using a
    balanced-panel approximation (average T̄ used for unbalanced panels).
    Under H₀ the statistic is approximately χ²(1).

    Args:
        df:          DataFrame (post missing-data strategy).
        dep_var:     Dependent variable column name.
        indep_vars:  Independent variable column names.
        entity_col:  Column identifying entities.
        time_col:    Column identifying time periods.

    Returns:
        BPLMResult with statistic, p_value, verdict, and a human note.
    """
    pooled = estimate_ols(df, dep_var, indep_vars)
    e = pooled.residuals  # indexed by original df rows (not MultiIndex)

    e_df = pd.DataFrame({"e": e, "entity": df.loc[e.index, entity_col]})

    entity_sum = e_df.groupby("entity")["e"].sum()   # Σₜ eᵢₜ
    entity_T   = e_df.groupby("entity")["e"].count() # T_i

    N     = len(entity_sum)
    T_bar = float(entity_T.mean())

    if T_bar < 2:
        return BPLMResult(
            statistic=float("nan"),
            p_value=float("nan"),
            verdict="pooled_ok",
            note="Average T < 2; BP-LM test not computed.",
        )

    sum_sq_sums  = float((entity_sum ** 2).sum())  # Σᵢ (Σₜ eᵢₜ)²
    sum_sq_resid = float((e_df["e"] ** 2).sum())   # Σᵢ Σₜ eᵢₜ²

    ratio = sum_sq_sums / sum_sq_resid
    lm    = (N * T_bar / (2.0 * (T_bar - 1.0))) * (ratio - 1.0) ** 2
    p     = float(1.0 - _chi2.cdf(lm, df=1))

    verdict = "re_preferred" if p < 0.05 else "pooled_ok"
    note    = (
        f"Computed from pooled-OLS residuals "
        f"({N} entities, T̅={T_bar:.1f}). χ²(1)."
    )
    return BPLMResult(
        statistic=round(lm, 4),
        p_value=round(p, 4),
        verdict=verdict,
        note=note,
    )


@dataclass
class HausmanResult:
    """Result of the Hausman FE-vs-RE specification test."""
    statistic: float
    p_value: float
    dof: int
    verdict: str    # "fe_preferred" | "re_preferred" | "borderline"
    note: str


def hausman_test(fe_model: FittedModel, re_model: FittedModel) -> HausmanResult:
    """Hausman test: Fixed Effects vs Random Effects.

    H₀: both FE and RE are consistent — prefer RE (efficient).
    H₁: only FE is consistent — RE is biased by correlated effects.

    H = (b_FE − b_RE)ᵀ (V_FE − V_RE)⁻¹ (b_FE − b_RE)  ~ χ²(k)

    where k = number of common time-varying regressors (constant excluded).
    If V_FE − V_RE is not positive definite we use the Moore-Penrose
    pseudoinverse and adjust the degrees of freedom to the matrix rank.

    Args:
        fe_model: FittedModel returned by estimate_fe().
        re_model: FittedModel returned by estimate_re().

    Returns:
        HausmanResult.
    """
    # Common regressors: FE has no const, RE has const — exclude it.
    fe_vars  = list(fe_model.params.index)
    re_vars  = [v for v in re_model.params.index if v != "const"]
    common   = [v for v in fe_vars if v in re_vars]

    if not common:
        return HausmanResult(
            statistic=float("nan"),
            p_value=float("nan"),
            dof=0,
            verdict="re_preferred",
            note="No common regressors between FE and RE — Hausman test skipped.",
        )

    b_fe = fe_model.params[common].to_numpy()
    b_re = re_model.params[common].to_numpy()
    diff = b_fe - b_re

    # Full covariance matrices from linearmodels result (.cov property)
    try:
        V_fe_full = fe_model._result.cov.values
        V_re_full = re_model._result.cov.values

        fe_idx = [list(fe_model.params.index).index(v) for v in common]
        re_idx = [list(re_model.params.index).index(v) for v in common]

        V_fe = V_fe_full[np.ix_(fe_idx, fe_idx)]
        V_re = V_re_full[np.ix_(re_idx, re_idx)]
    except Exception:
        # Fall back to diagonal approximation from standard errors
        V_fe = np.diag(fe_model.bse[common].to_numpy() ** 2)
        V_re = np.diag(re_model.bse[common].to_numpy() ** 2)

    V_diff = V_fe - V_re

    # Check positive definiteness; fall back to pseudoinverse if needed
    try:
        V_inv  = np.linalg.inv(V_diff)
        h_stat = float(diff @ V_inv @ diff)
        dof    = len(common)
    except np.linalg.LinAlgError:
        V_inv  = np.linalg.pinv(V_diff)
        h_stat = float(diff @ V_inv @ diff)
        dof    = int(np.linalg.matrix_rank(V_diff))

    if h_stat < 0:
        return HausmanResult(
            statistic=round(h_stat, 4),
            p_value=float("nan"),
            dof=dof,
            verdict="re_preferred",
            note=(
                "Hausman statistic is negative (V_FE − V_RE is not PSD). "
                "This can occur with small samples or near-multicollinearity. "
                "Defaulting to RE."
            ),
        )

    p = float(1.0 - _chi2.cdf(h_stat, df=dof))

    if p < 0.04:
        verdict = "fe_preferred"
    elif p <= 0.06:
        verdict = "borderline"
    else:
        verdict = "re_preferred"

    note = (
        f"χ²({dof}) = {h_stat:.4f}, p = {p:.4f}. "
        f"Common regressors: {', '.join(common)}."
    )
    return HausmanResult(
        statistic=round(h_stat, 4),
        p_value=round(p, 4),
        dof=dof,
        verdict=verdict,
        note=note,
    )
