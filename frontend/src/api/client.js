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

export async function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE}/upload`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
  return res.json()
}

export async function getStats() {
  const res = await fetch(`${BASE}/stats`)
  if (!res.ok) throw new Error('Stats fetch failed')
  return res.json()
}

export async function listDocuments() {
  const res = await fetch(`${BASE}/documents`)
  if (!res.ok) throw new Error('List failed')
  return res.json()
}

export async function deleteDocument(name) {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error('Delete failed')
  return res.json()
}
