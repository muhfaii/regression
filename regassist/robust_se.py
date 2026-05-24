"""
HC and CR variant selection, application, and reporting.

HC (heteroskedasticity-consistent) applies to cross-sectional OLS.
CR (cluster-robust) applies to panel FE/RE.

Selection logic follows PRD companion doc §2.2 (HC) and §3.3 (CR).
CR2 implemented manually per Imbens & Kolesár (2016); HC4 omitted (not in statsmodels).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import t as _t

from regassist.estimate import FittedModel


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class LeverageSummary:
    max_leverage: float
    n_high: int            # observations with h_i > 2k/n
    n_extreme: int         # observations with h_i > 4k/n
    threshold_high: float  # 2k/n
    threshold_extreme: float  # 4k/n


@dataclass
class SESelection:
    variant: str               # e.g. "HC3", "CR1"
    justification: str         # one-line why (for report methods section)
    citation: str              # report-ready citation string
    leverage: LeverageSummary | None = None   # OLS only
    few_cluster_warning: str | None = None    # panel only (G < 20)


# ---------------------------------------------------------------------------
# HC variant selection (cross-sectional OLS)
# ---------------------------------------------------------------------------

_HC_CITATIONS: dict[str, str] = {
    "HC0": (
        "Standard errors are HC0 heteroskedasticity-consistent (White, 1980)."
    ),
    "HC1": (
        "Standard errors are HC1 heteroskedasticity-consistent "
        "(White, 1980; with degrees-of-freedom correction)."
    ),
    "HC2": (
        "Standard errors are HC2 heteroskedasticity-consistent "
        "(MacKinnon & White, 1985)."
    ),
    "HC3": (
        "Standard errors are HC3 heteroskedasticity-consistent "
        "(MacKinnon & White, 1985)."
    ),
}

_VALID_HC = {"Auto", "HC0", "HC1", "HC2", "HC3"}


def select_hc_variant(
    n: int,
    k: int,
    hat_values: np.ndarray,
    override: str | None = None,
) -> SESelection:
    """Select an HC variant following PRD §2.2 selection rules.

    Args:
        n:          Sample size (number of observations).
        k:          Number of parameters including the constant.
        hat_values: Hat-matrix diagonal (leverage values), length n.
        override:   User-specified variant string, or None / "Auto" for auto.

    Returns:
        SESelection with chosen variant, justification, citation, and leverage summary.
    """
    lev = _compute_leverage_summary(n, k, hat_values)

    if override and override != "Auto":
        if override not in _VALID_HC - {"Auto"}:
            raise ValueError(
                f"Unknown HC variant override {override!r}. "
                f"Valid: {sorted(_VALID_HC - {'Auto'})}."
            )
        variant = override
        just = f"{variant} was manually selected (override)."
    elif n < 250:
        variant = "HC3"
        just = (
            f"HC3 selected: sample size (n = {n}) is below 250, "
            "where HC3 outperforms HC1 in finite-sample performance "
            "(Long & Ervin, 2000)."
        )
    elif lev.n_extreme > 0:
        variant = "HC3"
        just = (
            f"HC3 selected: {lev.n_extreme} observation(s) have extreme leverage "
            f"(h_i > 4k/n = {lev.threshold_extreme:.4f}). "
            "HC3's heavier jackknife correction is warranted."
        )
    elif lev.n_high > 0:
        variant = "HC3"
        just = (
            f"HC3 selected: {lev.n_high} observation(s) have high leverage "
            f"(h_i > 2k/n = {lev.threshold_high:.4f}). "
            "HC3 corrects for leverage influence on residual weighting."
        )
    else:
        variant = "HC1"
        just = (
            f"HC1 selected: sample size (n = {n}) ≥ 250 and no high-leverage "
            "observations detected. HC1 matches Stata's default and "
            "standard published practice."
        )

    return SESelection(
        variant=variant,
        justification=just,
        citation=_HC_CITATIONS.get(
            variant,
            f"Standard errors are {variant} heteroskedasticity-consistent.",
        ),
        leverage=lev,
    )


def get_hat_values(model: FittedModel) -> np.ndarray:
    """Compute leverage (hat-matrix diagonal) for an OLS FittedModel."""
    from statsmodels.stats.outliers_influence import OLSInfluence
    return OLSInfluence(model._result).hat_matrix_diag


def _compute_leverage_summary(n: int, k: int, hat_values: np.ndarray) -> LeverageSummary:
    thresh_high = 2 * k / n
    thresh_extreme = 4 * k / n
    return LeverageSummary(
        max_leverage=float(np.max(hat_values)),
        n_high=int(np.sum(hat_values > thresh_high)),
        n_extreme=int(np.sum(hat_values > thresh_extreme)),
        threshold_high=thresh_high,
        threshold_extreme=thresh_extreme,
    )


# ---------------------------------------------------------------------------
# CR variant selection (panel FE / RE)
# ---------------------------------------------------------------------------

_CR_CITATIONS: dict[str, str] = {
    "CR0": "Standard errors are clustered at the entity level (CR0).",
    "CR1": (
        "Standard errors are clustered at the entity level "
        "(CR1, Liang & Zeger, 1986)."
    ),
    "CR2": (
        "Standard errors are clustered at the entity level with "
        "small-cluster correction (CR2, Imbens & Kolesár, 2016)."
    ),
}

_VALID_CR = {"Auto", "CR0", "CR1", "CR2"}


def select_cr_variant(
    n_clusters: int,
    override: str | None = None,
) -> SESelection:
    """Select a CR variant following PRD §3.3 selection rules.

    Args:
        n_clusters: Number of clusters (entities) G.
        override:   User-specified variant string, or None / "Auto" for auto.

    Returns:
        SESelection with chosen variant, justification, citation, and
        (when G < 20) a few-cluster warning.
    """
    few_cluster_warning: str | None = None

    if override and override != "Auto":
        if override not in _VALID_CR - {"Auto"}:
            raise ValueError(
                f"Unknown CR variant override {override!r}. "
                f"Valid: {sorted(_VALID_CR - {'Auto'})}."
            )
        variant = override
        just = f"{variant} was manually selected (override)."
    elif n_clusters >= 50:
        variant = "CR1"
        just = (
            f"CR1 selected: {n_clusters} clusters ≥ 50, meeting the threshold "
            "for reliable cluster-robust inference "
            "(standard practice; matches Stata default)."
        )
    elif n_clusters >= 20:
        variant = "CR2"
        just = (
            f"CR2 selected: {n_clusters} clusters < 50. "
            "CR2 applies the small-cluster correction "
            "(Imbens & Kolesár, 2016) recommended when G < 50."
        )
    else:
        variant = "CR2"
        just = (
            f"CR2 selected: {n_clusters} clusters < 20. "
            "CR2 applies the Imbens & Kolesár (2016) small-cluster correction; "
            "inference remains fragile."
        )
        few_cluster_warning = (
            f"Your panel has **{n_clusters} entities**, which is below the "
            "threshold for reliable cluster-robust inference. CR2 standard errors "
            "are applied but p-values should be interpreted cautiously. "
            "For more reliable inference with few clusters, consider wild cluster "
            "bootstrap (Cameron, Gelbach & Miller, 2008) — outside this tool's "
            "current scope."
        )

    return SESelection(
        variant=variant,
        justification=just,
        citation=_CR_CITATIONS.get(
            variant,
            f"Standard errors are {variant} clustered at the entity level.",
        ),
        few_cluster_warning=few_cluster_warning,
    )


# ---------------------------------------------------------------------------
# Application — OLS / HC
# ---------------------------------------------------------------------------

def apply_hc(model: FittedModel, selection: SESelection) -> FittedModel:
    """Return a new FittedModel with HC-corrected SEs (OLS only).

    Uses statsmodels get_robustcov_results, which supports HC0–HC3.
    Params, residuals, fitted values, R², and X/y are unchanged.
    """
    robust_res = model._result.get_robustcov_results(cov_type=selection.variant)

    ci_arr = robust_res.conf_int()
    ci = pd.DataFrame(ci_arr, index=model.params.index, columns=["lower_95", "upper_95"])

    return dataclasses.replace(
        model,
        bse=pd.Series(robust_res.bse, index=model.params.index),
        tvalues=pd.Series(robust_res.tvalues, index=model.params.index),
        pvalues=pd.Series(robust_res.pvalues, index=model.params.index),
        conf_int=ci,
        se_variant=selection.variant,
        se_justification=selection.justification,
        se_citation=selection.citation,
        leverage_summary=selection.leverage,
    )


# ---------------------------------------------------------------------------
# Application — Panel / CR
# ---------------------------------------------------------------------------

def apply_cr(model: FittedModel, selection: SESelection) -> FittedModel:
    """Return a new FittedModel with CR-corrected SEs (panel FE/RE).

    CR0, CR1: standard cluster-robust sandwich.
    CR2: Imbens & Kolesár (2016) leverage-adjusted sandwich (FE only).
         For RE models, CR2 falls back to CR1 (quasi-demeaning complicates
         the CR2 projection matrix; CR1 is the standard applied remedy).

    The entity grouping is read from model.X.index (panel MultiIndex).
    """
    entity_labels = model.X.index.get_level_values(0).to_numpy()
    n_clusters = len(np.unique(entity_labels))

    variant = selection.variant

    if variant == "CR2" and model.model_type != "fe":
        # CR2 for RE: fall back to CR1 (see docstring)
        variant = "CR1"

    X_np, e_np = _get_panel_arrays(model)

    if variant == "CR2":
        bse, tv, pv, ci = _cr2(X_np, e_np, entity_labels, model)
    else:
        dof_scale = _cr_dof_scale(variant, X_np, entity_labels)
        bse, tv, pv, ci = _cr_sandwich_result(X_np, e_np, entity_labels, dof_scale, model)

    return dataclasses.replace(
        model,
        bse=bse,
        tvalues=tv,
        pvalues=pv,
        conf_int=ci,
        se_variant=variant,
        se_justification=selection.justification,
        se_citation=selection.citation,
        leverage_summary=None,
        n_clusters=n_clusters,
    )


# ---------------------------------------------------------------------------
# CR internals
# ---------------------------------------------------------------------------

def _get_panel_arrays(model: FittedModel) -> tuple[np.ndarray, np.ndarray]:
    """Return (X_np, e_np) for the panel CR sandwich.

    FE: X is within-entity demeaned (to match FE residuals which are already demeaned).
    RE: X is used as-is (raw, including const); RE residuals include the entity component.
    """
    X_raw = model.X.values.astype(float)
    e = model.residuals.values.astype(float)
    entity_labels = model.X.index.get_level_values(0).to_numpy()

    if model.model_type == "fe":
        # Within-entity demean X to match the within-estimator space
        X_dm = X_raw.copy()
        for g in np.unique(entity_labels):
            mask = entity_labels == g
            X_dm[mask] -= X_dm[mask].mean(axis=0)
        return X_dm, e
    else:
        # RE: use raw X
        return X_raw, e


def _cr_dof_scale(variant: str, X: np.ndarray, entity_labels: np.ndarray) -> float:
    """Degrees-of-freedom scaling factor for CR0 and CR1."""
    if variant == "CR0":
        return 1.0
    # CR1: (G / (G-1)) * (n-1) / (n-k)  — matches Stata vce(cluster) for xtreg,fe
    G = len(np.unique(entity_labels))
    n, k = X.shape
    return (G / (G - 1)) * ((n - 1) / (n - k))


def _cr_sandwich_result(
    X: np.ndarray,
    e: np.ndarray,
    entity_labels: np.ndarray,
    dof_scale: float,
    model: FittedModel,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    """Compute V = dof_scale * M * B * M and convert to SE + inference."""
    k = X.shape[1]
    M = np.linalg.inv(X.T @ X)
    B = np.zeros((k, k))
    for g in np.unique(entity_labels):
        mask = entity_labels == g
        score_g = X[mask].T @ e[mask]
        B += np.outer(score_g, score_g)
    V = dof_scale * (M @ B @ M)
    return _vcov_to_inference(V, model)


def _cr2(
    X: np.ndarray,
    e: np.ndarray,
    entity_labels: np.ndarray,
    model: FittedModel,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    """CR2 sandwich with Imbens-Kolesár leverage adjustment.

    A_g = (I_g - H_gg)^{-1/2}  via eigendecomposition,
    where H_gg = X_g (X'X)^{-1} X_g' is the within-cluster hat block.
    """
    k = X.shape[1]
    M = np.linalg.inv(X.T @ X)
    B = np.zeros((k, k))

    for g in np.unique(entity_labels):
        mask = entity_labels == g
        X_g = X[mask]           # T_g × k
        e_g = e[mask]           # T_g

        H_gg = X_g @ M @ X_g.T   # T_g × T_g leverage block
        I_g = np.eye(len(X_g))
        inner = I_g - H_gg

        # A_g = (I - H_gg)^{-1/2} via symmetric eigendecomposition
        eigvals, eigvecs = np.linalg.eigh(inner)
        eigvals = np.maximum(eigvals, 1e-10)   # numerical floor for near-zero eigenvalues
        A_g = eigvecs @ np.diag(1.0 / np.sqrt(eigvals)) @ eigvecs.T

        score_g = X_g.T @ A_g @ e_g
        B += np.outer(score_g, score_g)

    V = M @ B @ M
    return _vcov_to_inference(V, model)


def _vcov_to_inference(
    V: np.ndarray,
    model: FittedModel,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.DataFrame]:
    """Derive bse, tvalues, pvalues, conf_int from a covariance matrix."""
    idx = model.params.index
    se = pd.Series(np.sqrt(np.diag(V)), index=idx)
    tv = model.params / se

    dof = int(model.n_obs) - int(model.n_params)
    dof = max(dof, 1)
    pv = pd.Series(2.0 * _t.sf(np.abs(tv.values), df=dof), index=idx)

    margin = _t.ppf(0.975, df=dof) * se
    ci = pd.DataFrame({
        "lower_95": model.params - margin,
        "upper_95": model.params + margin,
    })

    return se, tv, pv, ci
