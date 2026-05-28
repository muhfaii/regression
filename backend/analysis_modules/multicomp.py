"""Multiple comparison corrections — wraps statsmodels.stats.multitest."""
from __future__ import annotations

import numpy as np
from statsmodels.stats.multitest import multipletests


_METHODS = {
    "bonferroni": "bonferroni",
    "holm": "holm",
    "fdr_bh": "fdr_bh",
    "fdr_by": "fdr_by",
    "sidak": "sidak",
}


def adjust_pvalues(
    p_values: list[float] | np.ndarray,
    method: str = "fdr_bh",
) -> np.ndarray:
    """Adjust p-values for multiple comparisons.

    Parameters
    ----------
    p_values : list[float] | np.ndarray
        Raw p-values to adjust.
    method : str
        One of 'bonferroni', 'holm', 'fdr_bh', 'fdr_by', 'sidak'.

    Returns
    -------
    np.ndarray
        Adjusted p-values (same shape as input).
    """
    method = method.lower().strip()
    if method not in _METHODS:
        raise ValueError(f"Unknown correction method: {method!r}. Choose from {list(_METHODS)}.")

    p = np.asarray(p_values, dtype=float)
    if p.size == 0:
        return p

    _, p_corrected, _, _ = multipletests(p, method=_METHODS[method])
    return p_corrected
