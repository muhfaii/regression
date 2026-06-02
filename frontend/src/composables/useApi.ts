import { useAuthStore } from '../stores/auth'

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

  return {
    uploadFile, listSamples, loadSample, pasteData,
    runAnalysis, validateConfig,
    exportWord, createShareLink, getSharedResult,
  }
}
