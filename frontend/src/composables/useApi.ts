const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `Request failed: ${res.status}`)
  }
  return res.json()
}

export function useApi() {
  async function uploadFile(file: File) {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`${BASE}/data/upload`, { method: 'POST', body: form })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? 'Upload failed')
    }
    return res.json()
  }

  async function listSamples() {
    return request<{ id: string; label: string; description: string }[]>('/data/samples')
  }

  async function loadSample(id: string) {
    return request(`/data/samples/${id}`)
  }

  async function pasteData(text: string) {
    const res = await fetch(`${BASE}/data/paste`, {
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

  async function runAnalysis(payload: object) {
    return request('/analysis/run', { method: 'POST', body: JSON.stringify(payload) })
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
