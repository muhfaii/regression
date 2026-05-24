"""
Regression Assistant — Phase 2 (panel pipeline)
Streamlit entry point.

Run with:  streamlit run app.py
"""
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from regassist.detect import DetectionResult, detect_structure
from regassist.ingest import IngestResult, apply_missing_strategy, load_file
from regassist.validate import validate_spec
from regassist.pipeline import run_cross_sectional_pipeline, run_panel_pipeline
from regassist.report import build_report_data_from_pipeline, render_html

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Regression Assistant",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------

defaults = {
    "ingest_result": None,
    "detection_result": None,
    "structure_confirmed": False,   # True once user clicks Confirm / Override
    "confirmed_structure": None,    # the structure the user settled on
    "df_clean": None,
    "missing_strategy": None,
    "dep_var": None,
    "indep_vars": [],
    "report_html": None,
    "analysis_error": None,         # persists across rerun so the error stays visible
    "pipeline_warnings": [],        # persists across rerun (e.g. absorbed FE variables)
    "_last_filename": None,
    "robust_se_override": "Auto",   # HC or CR variant override
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_downstream(from_step: int) -> None:
    if from_step <= 1:
        st.session_state.ingest_result = None
        st.session_state.detection_result = None
        st.session_state.structure_confirmed = False
        st.session_state.confirmed_structure = None
        st.session_state.missing_strategy = None
        st.session_state.df_clean = None
        st.session_state.dep_var = None
        st.session_state.indep_vars = []
        st.session_state.report_html = None
        st.session_state.pipeline_warnings = []
    if from_step <= 2:
        st.session_state.structure_confirmed = False
        st.session_state.confirmed_structure = None
        st.session_state.missing_strategy = None
        st.session_state.df_clean = None
        st.session_state.dep_var = None
        st.session_state.indep_vars = []
        st.session_state.report_html = None
        st.session_state.pipeline_warnings = []
    if from_step <= 3:
        st.session_state.missing_strategy = None
        st.session_state.df_clean = None
        st.session_state.dep_var = None
        st.session_state.indep_vars = []
        st.session_state.report_html = None
        st.session_state.pipeline_warnings = []
    if from_step <= 4:
        st.session_state.dep_var = None
        st.session_state.indep_vars = []
        st.session_state.report_html = None
        st.session_state.pipeline_warnings = []


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("📊 Regression Assistant")
st.caption(
    "Upload your data, specify your model, and get a full diagnostic report."
)
st.divider()

# ---------------------------------------------------------------------------
# Step 1 — File upload
# ---------------------------------------------------------------------------

st.subheader("Step 1 — Upload your data")

uploaded = st.file_uploader(
    "Drag and drop or browse for a file",
    type=["csv", "xlsx"],
    help="CSV or Excel (.xlsx). Maximum 100 MB.",
)

if uploaded is not None:
    raw = uploaded.read()
    if uploaded.name != st.session_state._last_filename:
        st.session_state._last_filename = uploaded.name
        reset_downstream(1)
        try:
            result: IngestResult = load_file(raw, uploaded.name)
            st.session_state.ingest_result = result
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

result: IngestResult | None = st.session_state.ingest_result
if result is None:
    st.stop()

st.success(
    f"Loaded **{result.row_count:,}** rows and **{len(result.columns)}** columns "
    f"from `{uploaded.name}`."
)

with st.expander("Preview (first 10 rows)", expanded=True):
    st.dataframe(result.df.head(10), use_container_width=True)

with st.expander("Column summary"):
    summary_rows = [
        {
            "Column": c.name,
            "Type": c.dtype,
            "Missing": c.missing_count,
            "Missing %": f"{c.missing_pct:.1f}%",
            "⚠️ Check": "Looks numeric" if c.has_masked_numeric else "",
        }
        for c in result.columns
    ]
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Step 2 — Data structure detection & confirmation
# ---------------------------------------------------------------------------

st.subheader("Step 2 — Data structure")

# Run detection once per upload
if st.session_state.detection_result is None:
    st.session_state.detection_result = detect_structure(result.df)

det: DetectionResult = st.session_state.detection_result

# ── Time-series: block with clear Phase 2 message ──────────────────────────
if det.structure == "time_series" and not st.session_state.structure_confirmed:
    st.error(
        "**Time-series data detected** — this is not supported in Phase 1. "
        "Time-series diagnostics (stationarity, autocorrelation, ARCH) are planned for Phase 2."
    )
    st.info(
        f"Detected time column: **{det.time_col}** ({det.n_periods} periods). "
        "If this is incorrect, use the override below."
    )
    with st.expander("Override detection"):
        override = st.selectbox(
            "Treat this data as:",
            ["— select —", "cross_sectional", "panel"],
            key="ts_override",
        )
        if override != "— select —" and st.button("Apply override"):
            st.session_state.structure_confirmed = True
            st.session_state.confirmed_structure = override
            st.rerun()
    st.stop()

# ── Confirmation card for panel / cross-sectional / ambiguous ───────────────
if not st.session_state.structure_confirmed:
    _ICONS = {"panel": "🗂️", "cross_sectional": "📋", "ambiguous": "❓"}
    _LABELS = {"panel": "Panel data", "cross_sectional": "Cross-sectional data", "ambiguous": "Ambiguous"}
    _CONF_COLOR = {"high": "success", "medium": "info", "low": "warning"}

    icon  = _ICONS.get(det.structure, "📊")
    label = _LABELS.get(det.structure, det.structure)
    conf_fn = getattr(st, _CONF_COLOR.get(det.confidence, "info"))

    if det.structure == "panel":
        conf_fn(
            f"{icon} **{label} detected** (confidence: {det.confidence}) — "
            f"**{det.n_entities}** entities × **{det.n_periods}** time periods "
            f"= {result.row_count:,} observations.  \n"
            f"Entity column: `{det.entity_col}` · Time column: `{det.time_col}`"
        )
    elif det.structure == "cross_sectional":
        conf_fn(
            f"{icon} **{label} detected** (confidence: {det.confidence}) — "
            f"**{result.row_count:,}** observations, no repeated entity structure found."
        )
    else:
        st.warning(
            f"{icon} **Structure ambiguous** — could not automatically determine "
            "whether this is cross-sectional or panel data. Please select below."
        )

    # Reasoning expander
    with st.expander("Why was this detected?"):
        for line in det.reasoning:
            st.write(f"• {line}")
        if det.entity_candidates:
            st.write(f"**Entity candidates:** {', '.join(det.entity_candidates)}")
        if det.time_candidates:
            st.write(f"**Time candidates:** {', '.join(det.time_candidates)}")

    # Panel note: full pipeline coming in Phase 2
    if det.structure == "panel":
        st.info(
            "ℹ️ Full panel estimation (Fixed Effects / Random Effects / Hausman test) "
            "is coming in Phase 2. This run will use pooled OLS."
        )

    # Confirm / override
    col_confirm, col_override = st.columns([1, 2])
    with col_confirm:
        if st.button("✓ Confirm", type="primary", key="confirm_structure"):
            st.session_state.structure_confirmed = True
            st.session_state.confirmed_structure = det.structure
            st.rerun()

    with col_override:
        with st.expander("Override detection"):
            options = ["— select —", "cross_sectional", "panel"]
            override = st.selectbox("Treat this data as:", options, key="structure_override")
            if override != "— select —" and st.button("Apply override", key="apply_override"):
                st.session_state.structure_confirmed = True
                st.session_state.confirmed_structure = override
                reset_downstream(3)
                st.rerun()

    st.stop()

# Confirmed — show a compact summary
_confirmed = st.session_state.confirmed_structure
if _confirmed == "panel":
    st.success(f"🗂️ **Panel data confirmed** — {det.n_entities} entities × {det.n_periods} periods. Using pooled OLS (Phase 1).")
else:
    st.success(f"📋 **Cross-sectional data confirmed** — {result.row_count:,} observations.")

st.divider()

# ---------------------------------------------------------------------------
# Step 3 — Handle missing data
# ---------------------------------------------------------------------------

st.subheader("Step 3 — Missing data")

if result.has_missing:
    for w in result.warnings:
        st.warning(w)

    strategy = st.radio(
        "How should missing values be handled?",
        options=["listwise", "mean", "abort"],
        format_func=lambda s: {
            "listwise": "Listwise deletion — drop rows with any missing value",
            "mean":     "Mean imputation — replace missing values with the column mean",
            "abort":    "Abort — I will fix the data and re-upload",
        }[s],
        key="missing_strategy_radio",
        horizontal=True,
    )

    if st.button("Apply", key="apply_missing"):
        reset_downstream(2)
        try:
            st.session_state.df_clean = apply_missing_strategy(result.df, strategy)
            st.session_state.missing_strategy = strategy
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

    if st.session_state.df_clean is None:
        st.stop()

    df = st.session_state.df_clean
    n_dropped = result.row_count - len(df)
    if n_dropped > 0:
        st.info(f"After listwise deletion: **{len(df):,}** rows remain ({n_dropped} dropped).")
    else:
        st.info(f"Missing values filled. **{len(df):,}** rows.")
else:
    for w in result.warnings:
        st.warning(w)
    st.success("No missing values detected.")
    if st.session_state.df_clean is None:
        st.session_state.df_clean = result.df.copy()

df: pd.DataFrame = st.session_state.df_clean
if df is None:
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Step 4 — Variable selection
# ---------------------------------------------------------------------------

st.subheader("Step 4 — Specify your model")

all_cols = list(df.columns)

# For panel data, entity and time columns cannot be regressors — hide them
# from the independent-variable selector and show an informational note.
_det: DetectionResult = st.session_state.detection_result
_confirmed = st.session_state.confirmed_structure
_panel_reserved: list[str] = []
if _confirmed == "panel" and _det.entity_col and _det.time_col:
    _panel_reserved = [_det.entity_col, _det.time_col]
    st.info(
        f"Panel model — **{_det.entity_col}** (entity) and **{_det.time_col}** (time) "
        "are reserved for the panel structure and cannot be used as regressors."
    )

dep_var = st.selectbox(
    "Dependent variable (Y)",
    options=["— select —"] + all_cols,
    index=(
        0 if st.session_state.dep_var is None
        else (["— select —"] + all_cols).index(st.session_state.dep_var)
        if st.session_state.dep_var in all_cols else 0
    ),
    help="The outcome variable your model is trying to explain.",
)
if dep_var == "— select —":
    dep_var = None

# Exclude entity/time cols (panel) and the chosen dep_var from the regressor list
remaining = [
    c for c in all_cols
    if c != dep_var and c not in _panel_reserved
] if dep_var else [c for c in all_cols if c not in _panel_reserved]

sel_col, all_col = st.columns([3, 1], vertical_alignment="bottom")
with all_col:
    select_all = st.checkbox(
        "Select all",
        value=False,
        help="Tick to pre-select every available column, then remove the ones you don't need.",
        disabled=not remaining,
    )
with sel_col:
    default_selection = (
        remaining if select_all
        else [v for v in st.session_state.indep_vars if v in remaining]
    )
    indep_vars = st.multiselect(
        "Independent variables (X₁, X₂, …)",
        options=remaining,
        default=default_selection,
        help="Pick one or more predictors. Use 'Select all' to start from the full list.",
    )

if dep_var or indep_vars:
    val = validate_spec(df, dep_var or "", indep_vars)
    for err in val.errors:
        st.error(err)
    for warn in val.warnings:
        st.warning(warn)

    if val.ok and dep_var and indep_vars:
        st.session_state.dep_var = dep_var
        st.session_state.indep_vars = indep_vars

        terms = " + ".join(f"β{i+1}·{v}" for i, v in enumerate(indep_vars))
        st.markdown(f"**Model:** {dep_var} = β₀ + {terms} + ε")

        st.divider()

        with st.expander("⚙ Advanced — Standard error variant"):
            _is_panel = (
                st.session_state.confirmed_structure == "panel"
                and st.session_state.detection_result.entity_col
                and st.session_state.detection_result.time_col
            )
            if _is_panel:
                _se_opts = ["Auto", "CR0", "CR1", "CR2"]
                _se_help = (
                    "Auto selects CR1 (G ≥ 50) or CR2 (G < 50) when a cluster-robust "
                    "test fires. Override to force a specific variant."
                )
            else:
                _se_opts = ["Auto", "HC0", "HC1", "HC2", "HC3"]
                _se_help = (
                    "Auto selects HC1 or HC3 based on sample size and leverage when "
                    "a heteroskedasticity test fires. Override to force a specific variant."
                )
            st.session_state.robust_se_override = st.selectbox(
                "Standard error variant",
                options=_se_opts,
                index=_se_opts.index(
                    st.session_state.robust_se_override
                    if st.session_state.robust_se_override in _se_opts
                    else "Auto"
                ),
                help=_se_help,
                key="se_override_select",
            )

        if st.session_state.analysis_error:
            st.error(st.session_state.analysis_error)

        if st.button("▶ Run Analysis", type="primary", use_container_width=True):
            st.session_state.report_html = None
            st.session_state.analysis_error = None
            st.session_state.pipeline_warnings = []
            with st.spinner("Running pipeline…"):
                try:
                    confirmed = st.session_state.confirmed_structure
                    det: DetectionResult = st.session_state.detection_result

                    _override = st.session_state.robust_se_override
                    if confirmed == "panel" and det.entity_col and det.time_col:
                        pipeline = run_panel_pipeline(
                            df, dep_var, indep_vars,
                            entity_col=det.entity_col,
                            time_col=det.time_col,
                            ingest_result=result,
                            missing_strategy=st.session_state.missing_strategy,
                            robust_se_override=_override,
                        )
                    else:
                        pipeline = run_cross_sectional_pipeline(
                            df, dep_var, indep_vars,
                            ingest_result=result,
                            missing_strategy=st.session_state.missing_strategy,
                            robust_se_override=_override,
                        )

                    rdata = build_report_data_from_pipeline(
                        result, pipeline,
                        missing_strategy=st.session_state.missing_strategy,
                    )
                    st.session_state.report_html = render_html(rdata)
                    st.session_state.pipeline_warnings = pipeline.warnings
                    st.rerun()
                except Exception as exc:
                    import traceback
                    st.session_state.analysis_error = (
                        f"Analysis failed: {exc}\n\n"
                        f"```\n{traceback.format_exc()}\n```"
                    )
                    st.rerun()

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

if st.session_state.report_html:
    st.divider()
    st.subheader("Report")

    for w in st.session_state.pipeline_warnings:
        st.warning(w)

    col_dl, _ = st.columns([1, 4])
    with col_dl:
        st.download_button(
            label="⬇ Download HTML",
            data=st.session_state.report_html,
            file_name="regression_report.html",
            mime="text/html",
        )

    components.html(st.session_state.report_html, height=3200, scrolling=True)
