export type AuthError = 'unauthorized' | 'network'

export async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: 'same-origin' })
  if (r.status === 401) throw { kind: 'unauthorized' as const }
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return (await r.json()) as T
}

export async function postEmpty(url: string): Promise<void> {
  const r = await fetch(url, { method: 'POST', credentials: 'same-origin' })
  if (!r.ok && r.status !== 204) throw new Error(`${r.status} ${r.statusText}`)
}

// --- Inbox types ---

export type InboxMessage = {
  id: string
  gmail_message_id: string
  internal_date: number
  from: string | null
  to: string | null
  body_preview: string | null
}

export type InboxThread = {
  id: string
  gmail_thread_id: string
  subject: string | null
  bucket_id: string | null
  recent_message: InboxMessage | null
}

export type InboxPage = {
  as_of: number
  page: number
  limit: number
  threads: InboxThread[]
}

export function getInbox(opts: { page?: number; limit?: number } = {}): Promise<InboxPage> {
  const params = new URLSearchParams()
  if (opts.page) params.set('page', String(opts.page))
  if (opts.limit) params.set('limit', String(opts.limit))
  const qs = params.toString()
  return getJSON<InboxPage>(`/api/inbox${qs ? `?${qs}` : ''}`)
}

export function getThread(id: string): Promise<InboxThread> {
  return getJSON<InboxThread>(`/api/threads/${encodeURIComponent(id)}`)
}

export async function getThreadsBatch(thread_ids: string[]): Promise<InboxThread[]> {
  // One round trip for N ids. Used by the SSE replay path: a single SSE event
  // can carry up to ~200 thread ids on a kickoff full sync, and N parallel
  // GET /api/threads/{id} calls would create avoidable connection churn.
  if (thread_ids.length === 0) return []
  const r = await fetch('/api/threads/batch', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ thread_ids }),
  })
  if (r.status === 401) throw { kind: 'unauthorized' as const }
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  const body = (await r.json()) as { threads: InboxThread[] }
  return body.threads
}

export async function requestRefresh(): Promise<void> {
  const r = await fetch('/api/inbox/refresh', { method: 'POST', credentials: 'same-origin' })
  if (r.status !== 202 && r.status !== 200) {
    throw new Error(`refresh failed: ${r.status}`)
  }
}
