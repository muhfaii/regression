import { useAuthStore } from '../stores/auth'
import type { DatasetPreview } from '../types/dataset'

const BASE = '/api'

function authHeaders(): Record<string, string> {
  const auth = useAuthStore()
  if (auth.token) {
    return { Authorization: `Bearer ${auth.token}` }
  }
  return {}
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...(init?.headers as Record<string, string> | undefined),
  }
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    if (res.status === 401) {
      const auth = useAuthStore()
      auth.clearAuth()
      window.location.href = '/login'
    }
    throw new Error(body.detail ?? `Request failed: ${res.status}`)
  }
  return res.json()
}

export function useApi() {
  function _query(conversationId?: string | null): string {
    return conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ''
  }

  async function uploadFile(file: File, conversationId?: string | null) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/data/upload${_query(conversationId)}`, { method: 'POST', body: form })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Upload failed')
    }
    return res.json()
  }

  async function listSamples() {
    return request<{ id: string; label: string; description: string }[]>('/data/samples')
  }

  async function loadSample(id: string, conversationId?: string | null) {
    return request(`/data/samples/${id}${_query(conversationId)}`)
  }

  async function pasteData(text: string, conversationId?: string | null) {
    const res = await fetch(`${BASE}/data/paste${_query(conversationId)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Paste import failed')
    }
    return res.json()
  }

  async function runAnalysis(payload: object, conversationId?: string | null) {
    const body = conversationId ? { ...payload, conversation_id: conversationId } : payload
    return request('/analysis/run', { method: 'POST', body: JSON.stringify(body) })
  }

  async function validateConfig(payload: object) {
    return request<{ conflicts: { slot: string; column: string; required_type: string; actual_type: string }[] }>(
      '/analysis/validate-config',
      { method: 'POST', body: JSON.stringify(payload) },
    )
  }

  async function applyMissingData(
    sessionId: string,
    columns: string[],
    strategy: 'listwise' | 'mean' | 'median' | 'mode' | 'constant',
    constant?: string | number,
  ) {
    return request<DatasetPreview>('/dataprep/missing', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, columns, strategy, constant }),
    })
  }

  async function recodeColumn(
    sessionId: string,
    sourceColumn: string,
    newColumnName: string,
    mapping: Record<string, string | number>,
    options?: { default?: string | number; overwrite?: boolean },
  ) {
    return request<DatasetPreview>('/dataprep/recode', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        source_column: sourceColumn,
        new_column_name: newColumnName,
        mapping,
        default: options?.default,
        overwrite: options?.overwrite ?? false,
      }),
    })
  }

  async function computeColumn(
    sessionId: string,
    newColumnName: string,
    expression: string,
    overwrite = false,
  ) {
    return request<DatasetPreview>('/dataprep/compute', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, new_column_name: newColumnName, expression, overwrite }),
    })
  }

  async function reverseScore(
    sessionId: string,
    columns: string[],
    minValue: number,
    maxValue: number,
    suffix = '_r',
    overwrite = false,
  ) {
    return request<DatasetPreview>('/dataprep/reverse-score', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, columns, min_value: minValue, max_value: maxValue, suffix, overwrite }),
    })
  }

  async function mergeDatasets(
    sessionId: string,
    file: File,
    leftOn: string,
    rightOn: string,
    how: 'inner' | 'left' | 'right' | 'outer',
  ) {
    const form = new FormData()
    form.append('session_id', sessionId)
    form.append('left_on', leftOn)
    form.append('right_on', rightOn)
    form.append('how', how)
    form.append('file', file)
    const res = await fetch(`${BASE}/dataprep/merge`, { method: 'POST', headers: authHeaders(), body: form })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Merge failed')
    }
    return res.json()
  }

  async function exportWord(resultId: string, sessionId: string): Promise<Blob> {
    const res = await fetch(
      `${BASE}/export/word/${resultId}?session_id=${encodeURIComponent(sessionId)}`,
      { method: 'POST' },
    )
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Export failed')
    }
    return res.blob()
  }

  async function createShareLink(resultId: string, sessionId: string) {
    return request<{ token: string; url: string }>(
      `/export/share/${resultId}?session_id=${encodeURIComponent(sessionId)}`,
      { method: 'POST' },
    )
  }

  async function getSharedResult(token: string) {
    return request<Record<string, unknown>>(`/share/${token}`)
  }

  async function getSessionLog(sessionId: string) {
    return request<{ filename: string; steps: { timestamp: number; action: string; detail: string }[] }>(
      `/export/log/${sessionId}`,
    )
  }

  async function downloadSessionLog(sessionId: string): Promise<Blob> {
    const res = await fetch(`${BASE}/export/log/${sessionId}/download`, { headers: authHeaders() })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Log download failed')
    }
    return res.blob()
  }

  async function exportReport(sessionId: string, resultIds?: string[]): Promise<Blob> {
    const res = await fetch(`${BASE}/export/report/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(resultIds ? { result_ids: resultIds } : {}),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Report export failed')
    }
    return res.blob()
  }

  async function createSessionShareLink(sessionId: string, resultIds?: string[]) {
    return request<{ token: string; url: string }>(`/export/share-session/${sessionId}`, {
      method: 'POST',
      body: JSON.stringify(resultIds ? { result_ids: resultIds } : {}),
    })
  }

  async function getSharedSession(token: string) {
    return request<{ filename: string; results: Record<string, unknown>[] }>(`/share/session/${token}`)
  }

  return {
    uploadFile, listSamples, loadSample, pasteData,
    applyMissingData, recodeColumn, computeColumn, reverseScore, mergeDatasets,
    runAnalysis, validateConfig,
    exportWord, createShareLink, getSharedResult,
    getSessionLog, downloadSessionLog, exportReport, createSessionShareLink, getSharedSession,
  }
}
