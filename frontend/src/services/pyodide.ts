import { ref, readonly, computed } from 'vue'

type LoadingStatus = 'idle' | 'loading-pyodide' | 'installing-packages' | 'loading-modules' | 'ready' | 'error'

interface PyodideProxy {
  runPython(code: string): any
  runPythonAsync(code: string): Promise<any>
  FS: {
    mkdirTree(path: string): void
    writeFile(path: string, data: string): void
  }
  loadPackage(names: string[]): Promise<void>
  pyimport(name: string): any
  globals: Map<string, any>
  isPyProxy(obj: any): boolean
}

const PYODIDE_CDN = 'https://cdn.jsdelivr.net/pyodide/v0.27.5/full/pyodide.js'
const PYODIDE_INDEX = 'https://cdn.jsdelivr.net/pyodide/v0.27.5/full/'

const status = ref<LoadingStatus>('idle')
const progressMsg = ref('')
const errorMessage = ref<string | null>(null)
const isReady = computed(() => status.value === 'ready')

let pyd: PyodideProxy | null = null
let ready = false

const BRIDGE_CODE = `

import json
import io
import sys
import pandas as pd

sys.path.insert(0, '/home/pyodide')

import analysis_modules.descriptive as descriptive
import analysis_modules.t_tests as t_tests
import analysis_modules.anova as anova
import analysis_modules.correlation as correlation
import analysis_modules.chi_square as chi_square
import analysis_modules.nonparametric as nonparametric
import analysis_modules.regression as regression
import analysis_modules.reliability as reliability
import analysis_modules.power_analysis as power_analysis
import analysis_modules.logistic as logistic
import analysis_modules.moderation as moderation
import analysis_modules.mediation as mediation
import analysis_modules.factor_analysis as factor_analysis
import analysis_modules.cfa as cfa
import analysis_modules.mixed_anova as mixed_anova
import analysis_modules.timeseries as timeseries
import analysis_modules.multicomp as multicomp

try:
    import regassist.ingest as _ingest
    _REGRESSION_READY = True
except Exception:
    _REGRESSION_READY = False

_current_df = None
_current_filename = None


def parse_file(data_bytes: bytes, filename: str) -> str:
    global _current_df, _current_filename
    _ingest_ = _ingest
    result = _ingest_.load_file(data_bytes, filename)
    _current_df = result.df
    _current_filename = filename
    return _build_preview(result.df, result)


def parse_text(text: str) -> str:
    global _current_df, _current_filename
    lines = text.strip().splitlines()
    sep = "\\t" if sum(l.count("\\t") for l in lines[:5]) >= sum(l.count(",") for l in lines[:5]) else ","
    _current_df = pd.read_csv(io.StringIO(text), sep=sep)
    _current_filename = "pasted_data.csv"

    class FakeCol:
        pass
    class FakeResult:
        pass

    cols = []
    for c in _current_df.columns:
        fc = FakeCol()
        fc.name = c
        fc.dtype = str(_current_df[c].dtype)
        fc.missing_count = int(_current_df[c].isnull().sum())
        fc.missing_pct = round(fc.missing_count / len(_current_df) * 100, 2) if len(_current_df) else 0.0
        fc.has_masked_numeric = False
        cols.append(fc)

    fr = FakeResult()
    fr.df = _current_df
    fr.row_count = len(_current_df)
    fr.columns = cols
    fr.warnings = []
    return _build_preview(_current_df, fr)


def _build_preview(df, ingest_result) -> str:
    columns = []
    for col in ingest_result.columns:
        series = df[col.name]
        inferred = _classify_type(series)
        columns.append({
            "name": col.name,
            "raw_dtype": str(col.dtype) if hasattr(col, 'dtype') else str(df[col.name].dtype),
            "inferred_type": inferred,
            "missing_count": col.missing_count,
            "missing_pct": col.missing_pct,
            "has_masked_numeric": getattr(col, 'has_masked_numeric', False),
        })

    ordinal_count = sum(1 for c in columns if c["inferred_type"] == "categorical" and _might_be_ordinal(df, c["name"]))
    ctx = "survey" if len(columns) > 0 and ordinal_count / len(columns) > 0.5 else "generic"

    preview = {
        "session_id": "pyodide",
        "filename": _current_filename,
        "row_count": ingest_result.row_count,
        "columns": columns,
        "dataset_context": ctx,
        "warnings": getattr(ingest_result, 'warnings', []),
        "conversation_id": None,
    }
    return json.dumps(preview, default=str)


def _classify_type(series):
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_numeric_dtype(series):
        vals = set(series.dropna().astype(int).unique())
        if vals <= {1,2,3,4,5} or vals <= {1,2,3,4,5,6,7}:
            return "ordinal"
        nunique = series.nunique()
        if nunique <= 10 and _all_integers(series):
            return "categorical"
        return "continuous"
    return "categorical"


def _might_be_ordinal(df, col_name):
    series = df[col_name]
    if not pd.api.types.is_numeric_dtype(series):
        return False
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    try:
        vals = set(non_null.astype(int).unique())
        return vals <= {1,2,3,4,5} or vals <= {1,2,3,4,5,6,7}
    except (ValueError, TypeError):
        return False


def _all_integers(series):
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    try:
        return (non_null == non_null.astype(int)).all()
    except (ValueError, TypeError):
        return False


_RUNNERS = {
    "descriptive": descriptive.run,
    "independent_t": t_tests.run_independent_t,
    "paired_t": t_tests.run_paired_t,
    "one_way_anova": anova.run,
    "factorial_anova": anova.run_factorial,
    "mann_whitney": nonparametric.run_mann_whitney,
    "wilcoxon": nonparametric.run_wilcoxon,
    "kruskal_wallis": nonparametric.run_kruskal_wallis,
    "correlation": correlation.run,
    "chi_square": chi_square.run,
    "reliability": reliability.run,
    "power_analysis": power_analysis.run,
    "timeseries": timeseries.run,
    "factor_analysis": factor_analysis.run,
    "mixed_anova": mixed_anova.run,
    "cfa": cfa.run,
}


if _REGRESSION_READY:
    _RUNNERS["ols_regression"] = _run_ols
    _RUNNERS["logistic_regression"] = logistic.run
    _RUNNERS["moderation"] = moderation.run
    _RUNNERS["mediation"] = mediation.run


def _run_ols(df, config, options):
    dep_var = config.get("dep_var")
    indep_vars = config.get("indep_vars", [])
    if not dep_var or not indep_vars:
        raise ValueError("dep_var and at least one indep_var are required.")
    return regression.run_ols(df, dep_var, indep_vars, options=options)


_SLOT_TYPES = {
    "descriptive": {"variables": "any"},
    "independent_t": {"outcome": "continuous", "group": "categorical"},
    "paired_t": {"col_a": "continuous", "col_b": "continuous"},
    "one_way_anova": {"outcome": "continuous", "group": "categorical"},
    "factorial_anova": {"outcome": "continuous", "factors": "categorical"},
    "mann_whitney": {"outcome": "continuous", "group": "categorical"},
    "wilcoxon": {"col_a": "continuous", "col_b": "continuous"},
    "kruskal_wallis": {"outcome": "continuous", "group": "categorical"},
    "correlation": {"variables": "continuous"},
    "chi_square": {"col_a": "categorical", "col_b": "categorical"},
    "ols_regression": {"dep_var": "continuous", "indep_vars": "any"},
    "logistic_regression": {"outcome": "categorical", "predictors": "any"},
    "moderation": {"outcome": "continuous", "predictor": "any", "moderator": "any", "covariates": "any"},
    "mediation": {"outcome": "continuous", "predictor": "any", "mediator": "any", "covariates": "any"},
    "reliability": {"variables": "any"},
    "timeseries": {"value": "continuous", "time_col": "any", "group_by": "categorical"},
    "factor_analysis": {"variables": "continuous"},
    "mixed_anova": {"outcome": "continuous", "within_factor": "categorical", "subject_id": "any", "between_factor": "categorical"},
    "cfa": {"indicators": "continuous"},
}


def validate_config(test_key: str, config_json: str, column_overrides_json: str = "{}") -> str:
    global _current_df
    if _current_df is None:
        return json.dumps({"conflicts": []})
    slot_types = _SLOT_TYPES.get(test_key, {})
    if not slot_types:
        return json.dumps({"conflicts": []})
    inferred = {col: _classify_type(_current_df[col]) for col in _current_df.columns}
    overrides = json.loads(column_overrides_json)
    effective = {**inferred, **overrides}
    config = json.loads(config_json)
    conflicts = []
    for slot_key, required_type in slot_types.items():
        if required_type == "any":
            continue
        value = config.get(slot_key)
        if value is None:
            continue
        col_names = value if isinstance(value, list) else [value]
        for col in col_names:
            actual = effective.get(col)
            if actual and actual != required_type:
                conflicts.append({
                    "slot": slot_key,
                    "column": col,
                    "required_type": required_type,
                    "actual_type": actual,
                })
    return json.dumps({"conflicts": conflicts})


def run_analysis(test_key: str, config_json: str, options_json: str = "{}") -> str:
    global _current_df
    if _current_df is None:
        raise ValueError("No dataset loaded")
    runner = _RUNNERS.get(test_key)
    if runner is None:
        raise ValueError(f"Test '{test_key}' requires server. Please run it via the server endpoint.")
    config = json.loads(config_json)
    options = json.loads(options_json)
    result = runner(_current_df, config, options)
    d = result.__dict__.copy()
    if result.effect_size:
        d["effect_size"] = result.effect_size.__dict__
    d["assumption_checks"] = [a.__dict__ for a in result.assumption_checks]
    d["interpretation"] = result.interpretation.__dict__
    return json.dumps(d, default=str)
`


function _loadScript(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${url}"]`)
    if (existing) { resolve(); return }
    const script = document.createElement('script')
    script.src = url
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Failed to load script: ${url}`))
    document.head.appendChild(script)
  })
}


async function initialize(): Promise<void> {
  if (ready) return
  if (status.value !== 'idle') return

  status.value = 'loading-pyodide'
  progressMsg.value = 'Loading Pyodide runtime...'

  try {
    await _loadScript(PYODIDE_CDN)
    const loadPyodideFn = (window as any).loadPyodide
    if (!loadPyodideFn) throw new Error('Pyodide did not initialize')

    pyd = (await loadPyodideFn({ indexURL: PYODIDE_INDEX })) as PyodideProxy

    status.value = 'installing-packages'
    progressMsg.value = 'Installing Python packages...'

    await pyd.loadPackage(['micropip'])
    const micropip = pyd.pyimport('micropip')
    await micropip.install(['statsmodels', 'scikit-learn'])

    status.value = 'loading-modules'
    progressMsg.value = 'Loading analysis modules...'

    const modules = import.meta.glob('../pyodide-src/**/*.py', {
      eager: true,
      query: '?raw',
      import: 'default',
    }) as Record<string, string>

    for (const [importPath, content] of Object.entries(modules)) {
      const relPath = importPath.replace('../pyodide-src/', '')
      const fsPath = `/home/pyodide/${relPath}`
      const dir = fsPath.substring(0, fsPath.lastIndexOf('/'))
      try { pyd.FS.mkdirTree(dir) } catch { /* dir exists */ }
      pyd.FS.writeFile(fsPath, content as string)
    }

    await pyd.runPythonAsync(BRIDGE_CODE)

    status.value = 'ready'
    progressMsg.value = ''
    ready = true
  } catch (e: any) {
    status.value = 'error'
    errorMessage.value = e.message || 'Failed to load Pyodide'
    progressMsg.value = ''
  }
}


function _ensureReady() {
  if (!ready || !pyd) throw new Error('Pyodide not ready. Call initialize() first.')
  return pyd
}


async function parseFile(file: File): Promise<Record<string, unknown>> {
  const p = _ensureReady()
  const buf = await file.arrayBuffer()
  const bytes = new Uint8Array(buf)
  const jsonStr = await p.runPythonAsync(
    `parse_file(bytes([${Array.from(bytes).join(',')}]), ${JSON.stringify(file.name || 'upload')})`
  )
  return JSON.parse(jsonStr as string)
}


async function parseText(text: string): Promise<Record<string, unknown>> {
  const p = _ensureReady()
  const jsonStr = await p.runPythonAsync(`parse_text(${JSON.stringify(text)})`)
  return JSON.parse(jsonStr as string)
}


async function runAnalysis(
  testKey: string,
  config: Record<string, unknown>,
  options: Record<string, unknown> = {},
): Promise<Record<string, unknown>> {
  const p = _ensureReady()
  const jsonStr = await p.runPythonAsync(
    `run_analysis(${JSON.stringify(testKey)}, ${JSON.stringify(JSON.stringify(config))}, ${JSON.stringify(JSON.stringify(options))})`
  )
  return JSON.parse(jsonStr as string)
}


async function validateConfig(
  testKey: string,
  config: Record<string, unknown>,
  columnOverrides: Record<string, string> = {},
): Promise<{ conflicts: Array<{ slot: string; column: string; required_type: string; actual_type: string }> }> {
  const p = _ensureReady()
  const jsonStr = await p.runPythonAsync(
    `validate_config(${JSON.stringify(testKey)}, ${JSON.stringify(JSON.stringify(config))}, ${JSON.stringify(JSON.stringify(columnOverrides))})`
  )
  return JSON.parse(jsonStr as string)
}


export function usePyodide() {
  return {
    isReady,
    loadingStatus: readonly(status),
    loadingProgress: readonly(progressMsg),
    loadingError: readonly(errorMessage),
    initialize,
    parseFile,
    parseText,
    runAnalysis,
    validateConfig,
    supportsTest: (key: string) => {
      if (!ready) return false
      try {
        pyd!.runPython(`_RUNNERS.get(${JSON.stringify(key)})`)
        return true
      } catch {
        return false
      }
    },
  }
}
