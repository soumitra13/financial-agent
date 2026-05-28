// In production (Vercel), VITE_API_URL is set to the Railway API origin.
// The /api prefix is always appended so FastAPI routes stay consistent.
const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}`
  : '/api'

// API key stored in localStorage for persistence across sessions
export const getApiKey = () => localStorage.getItem('fca_api_key') || ''
export const setApiKey = (key) => localStorage.setItem('fca_api_key', key)
export const clearApiKey = () => localStorage.removeItem('fca_api_key')

const headers = () => ({
  'Content-Type': 'application/json',
  'X-API-Key': getApiKey(),
})

async function req(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, { ...options, headers: headers() })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw { status: res.status, detail: data.detail || 'Request failed' }
  return data
}

export const api = {
  // ── Health ─────────────────────────────────────────────
  health: () => fetch(`${BASE}/health`).then(r => r.json()),

  // ── Tasks ──────────────────────────────────────────────
  listTasks:   (limit = 50) => req(`/tasks?limit=${limit}`),
  getTask:     (id)         => req(`/tasks/${id}`),
  getAudit:    (id)         => req(`/tasks/${id}/audit`),
  getStats:    ()           => req('/tasks/stats'),
  getEscalations: ()        => req('/tasks/escalations/open'),
  createTask:  (payload)    => req('/tasks', { method: 'POST', body: JSON.stringify(payload) }),

  // ── Auth / API Keys ────────────────────────────────────
  listKeys:  ()           => req('/auth/keys'),
  createKey: (name)       => req('/auth/keys', { method: 'POST', body: JSON.stringify({ name }) }),
  revokeKey: (id)         => req(`/auth/keys/${id}`, { method: 'DELETE' }),
}

// Poll a task until it reaches a terminal state
export async function pollTask(taskId, onUpdate, intervalMs = 3000, maxAttempts = 60) {
  let attempts = 0
  return new Promise((resolve, reject) => {
    const timer = setInterval(async () => {
      attempts++
      try {
        const task = await api.getTask(taskId)
        onUpdate(task)
        if (task.status === 'completed' || task.status === 'failed') {
          clearInterval(timer)
          resolve(task)
        }
        if (attempts >= maxAttempts) {
          clearInterval(timer)
          reject(new Error('Task timed out'))
        }
      } catch (err) {
        clearInterval(timer)
        reject(err)
      }
    }, intervalMs)
  })
}
