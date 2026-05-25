const BASE = '/api'

export async function sendMessage(question, sessionId) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`Server error: ${res.status}`)
  return res.json()
}

export async function getStats() {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error('Stats fetch failed')
  return res.json()
}

// ── Uploads ──────────────────────────────────────────────────────────────────

export async function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/uploads`, { method: 'POST', body: form })
  if (!res.ok) {
    let message = `Upload failed: ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) message = body.detail
    } catch {}
    throw new Error(message)
  }
  return res.json()
}

export async function listUploads() {
  const res = await fetch(`${BASE}/uploads`)
  if (!res.ok) throw new Error('List uploads failed')
  return res.json() // { uploads: string[] }
}

export async function deleteUpload(filename) {
  const res = await fetch(`${BASE}/uploads/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('Delete failed')
  return res.json()
}

// ── Laws ─────────────────────────────────────────────────────────────────────

export async function listLaws() {
  const res = await fetch(`${BASE}/laws`)
  if (!res.ok) throw new Error('List laws failed')
  return res.json() // { laws: [{filename, enabled}] }
}

export async function toggleLaw(filename, enabled) {
  const res = await fetch(`${BASE}/laws/${encodeURIComponent(filename)}/toggle`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  })
  if (!res.ok) throw new Error('Toggle failed')
  return res.json()
}
