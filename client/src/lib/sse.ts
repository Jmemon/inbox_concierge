// Thin typed wrapper around browser EventSource. Server emits messages of the
// shape `data: { "thread_ids": string[] }\n\n`. Comment frames (`: keepalive`)
// don't fire onmessage so we don't need to filter them.

export type ThreadIdsEvent = { thread_ids: string[] }

export type SseHandle = {
  close: () => void
}

export function openInboxStream(
  onMessage: (e: ThreadIdsEvent) => void,
  onError?: (e: Event) => void,
): SseHandle {
  console.log('[sse] constructing EventSource /api/sse')
  const es = new EventSource('/api/sse', { withCredentials: true })

  es.onmessage = (ev) => {
    try {
      const parsed = JSON.parse(ev.data) as ThreadIdsEvent
      if (parsed && Array.isArray(parsed.thread_ids)) {
        console.log('[sse] onmessage thread_ids.length=', parsed.thread_ids.length)
        onMessage(parsed)
      }
    } catch {
      // ignore malformed frames; SSE keepalives don't fire onmessage anyway
    }
  }

  if (onError) {
    es.onerror = (e) => {
      // readyState: 0=CONNECTING, 1=OPEN, 2=CLOSED
      console.warn('[sse] onerror readyState=', es.readyState, e)
      onError(e)
    }
  }

  return {
    close: () => {
      console.log('[sse] close() called readyState=', es.readyState)
      es.close()
    },
  }
}
