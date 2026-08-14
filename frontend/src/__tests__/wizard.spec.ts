import { describe, it, expect } from 'vitest'
import { ROOT_QUESTION, getBranch, resolveTest } from '../constants/wizard'

describe('wizard root question', () => {
  it('offers all top-level goals plus an unsure option', () => {
    const values = ROOT_QUESTION.options.map(o => o.value)
    expect(values).toEqual(
      expect.arrayContaining(['compare', 'describe', 'relate', 'predict', 'structure', 'change', null]),
    )
  })
})

describe('unresolved goal', () => {
  it('falls back to descriptive statistics when no goal is picked', () => {
    expect(resolveTest(null, {})).toEqual({
      test_key: 'descriptive',
      reason: expect.stringContaining('descriptive statistics'),
    })
  })
})

describe('compare branch', () => {
  it('plans design, outcome type, and normality for a 2-group continuous outcome', () => {
    const branch = getBranch('compare')!
    expect(branch.getSteps({ design: '2', outcome_type: 'continuous' }).map(s => s.id))
      .toEqual(['design', 'outcome_type', 'normal'])
  })

  it('skips normality when the outcome is categorical', () => {
    const branch = getBranch('compare')!
    expect(branch.getSteps({ design: '2', outcome_type: 'categorical' }).map(s => s.id))
      .toEqual(['design', 'outcome_type'])
  })

  it('skips outcome type and normality for factorial/repeated designs', () => {
    const branch = getBranch('compare')!
    expect(branch.getSteps({ design: 'factorial' }).map(s => s.id)).toEqual(['design'])
    expect(branch.getSteps({ design: 'repeated' }).map(s => s.id)).toEqual(['design'])
  })

  it.each([
    [{ design: '2', outcome_type: 'continuous', normal: 'yes' }, 'independent_t'],
    [{ design: '2', outcome_type: 'continuous', normal: 'no' }, 'mann_whitney'],
    [{ design: '3+', outcome_type: 'continuous', normal: 'yes' }, 'one_way_anova'],
    [{ design: '3+', outcome_type: 'continuous', normal: 'no' }, 'kruskal_wallis'],
    [{ design: 'paired', outcome_type: 'continuous', normal: 'yes' }, 'paired_t'],
    [{ design: 'paired', outcome_type: 'continuous', normal: 'no' }, 'wilcoxon'],
    [{ design: '2', outcome_type: 'categorical' }, 'chi_square'],
    [{ design: 'factorial' }, 'factorial_anova'],
    [{ design: 'repeated' }, 'mixed_anova'],
  ])('resolves %o to %s', (answers, expected) => {
    expect(resolveTest('compare', answers as any).test_key).toBe(expected)
  })
})

describe('describe branch', () => {
  it('resolves immediately with no follow-up steps', () => {
    const branch = getBranch('describe')!
    expect(branch.getSteps({})).toEqual([])
    expect(resolveTest('describe', {}).test_key).toBe('descriptive')
  })
})

describe('relate branch', () => {
  it('resolves to correlation for continuous and chi-square for categorical', () => {
    expect(resolveTest('relate', { outcome_type: 'continuous' }).test_key).toBe('correlation')
    expect(resolveTest('relate', { outcome_type: 'categorical' }).test_key).toBe('chi_square')
  })
})

describe('predict branch', () => {
  it('asks outcome type only for the simple regression path', () => {
    const branch = getBranch('predict')!
    expect(branch.getSteps({ predict_kind: 'simple' }).map(s => s.id)).toEqual(['predict_kind', 'outcome_type'])
    expect(branch.getSteps({ predict_kind: 'panel' }).map(s => s.id)).toEqual(['predict_kind'])
  })

  it.each([
    [{ predict_kind: 'simple', outcome_type: 'continuous' }, 'ols_regression'],
    [{ predict_kind: 'simple', outcome_type: 'categorical' }, 'logistic_regression'],
    [{ predict_kind: 'panel' }, 'panel_regression'],
    [{ predict_kind: 'moderation' }, 'moderation'],
    [{ predict_kind: 'mediation' }, 'mediation'],
  ])('resolves %o to %s', (answers, expected) => {
    expect(resolveTest('predict', answers as any).test_key).toBe(expected)
  })
})

describe('structure branch', () => {
  it.each([
    [{ structure_kind: 'reliability' }, 'reliability'],
    [{ structure_kind: 'efa' }, 'factor_analysis'],
    [{ structure_kind: 'cfa' }, 'cfa'],
  ])('resolves %o to %s', (answers, expected) => {
    expect(resolveTest('structure', answers as any).test_key).toBe(expected)
  })
})

describe('change branch', () => {
  it.each([
    [{ change_kind: 'series' }, 'timeseries'],
    [{ change_kind: 'event' }, 'survival_analysis'],
  ])('resolves %o to %s', (answers, expected) => {
    expect(resolveTest('change', answers as any).test_key).toBe(expected)
  })
})
