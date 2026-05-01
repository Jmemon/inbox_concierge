export type PreviewExample = {
  thread_id: string
  subject: string
  sender: string
  score: number
  rationale: string
  snippet: string
}

export type SseDataEvent =
  | { event: 'threads_updated'; thread_ids: string[] }
  | { event: 'bucket_draft_preview'; draft_id: string; positives: PreviewExample[]; near_misses: PreviewExample[] }
  | { event: 'extend_complete'; thread_ids: string[]; more: boolean }

export type SseConnEvent = { event: '_open' } | { event: '_error' }
export type SseEvent = SseDataEvent | SseConnEvent

let _es: EventSource | null = null
const _handlers = new Set<(e: SseEvent) => void>()

export function subscribeSse(handler: (e: SseEvent) => void): () => void {
  _handlers.add(handler)
  if (!_es) _open()
  return () => {
    _handlers.delete(handler)
    if (_handlers.size === 0) _close()
  }
}

function _open() {
  console.log('[sse] opening EventSource')
  _es = new EventSource('/api/sse', { withCredentials: true })
  _es.onopen = () => { for (const h of _handlers) h({ event: '_open' }) }
  _es.onmessage = (ev) => {
    try {
      const parsed = JSON.parse(ev.data) as SseDataEvent
      if (parsed && typeof parsed === 'object' && (parsed as any).event) {
        for (const h of _handlers) h(parsed)
      }
    } catch { /* malformed frame; ignore */ }
  }
  _es.onerror = () => {
    for (const h of _handlers) h({ event: '_error' })
    _close()
    if (_handlers.size > 0) queueMicrotask(_open)
  }
}

function _close() { _es?.close(); _es = null }
