// Tiny fetch wrapper. One function per backend endpoint.
//
// The Vite dev server proxies /api/* to http://localhost:8000, so we use
// relative URLs everywhere. That means this code works the same in dev
// and in any production deployment that serves frontend + backend behind
// one host.

const handle = async (response) => {
  if (response.ok) return response.json()
  const body = await response.json().catch(() => ({}))
  throw new Error(body.detail || `HTTP ${response.status}`)
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const api = {
  listUsers: () =>
    fetch('/api/users').then(handle),

  listTickets: (userId, filters = {}) => {
    const qs = new URLSearchParams()
    Object.entries(filters).forEach(([k, v]) => {
      if (v) qs.set(k, v)
    })
    const suffix = qs.toString() ? `?${qs}` : ''
    return fetch(`/api/users/${userId}/tickets${suffix}`).then(handle)
  },

  getConversation: (userId) =>
    fetch(`/api/users/${userId}/conversation`).then(handle),

  sendMessage: (userId, message) =>
    fetch(`/api/users/${userId}/chat`, json('POST', { message })).then(handle),

  resetConversation: (userId) =>
    fetch(`/api/users/${userId}/conversation/reset`, json('POST', {})).then(handle),
}
