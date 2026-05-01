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
  const es = new EventSource('/api/sse', { withCredentials: true })
  es.onmessage = (ev) => {
    try {
      const parsed = JSON.parse(ev.data) as ThreadIdsEvent
      if (parsed && Array.isArray(parsed.thread_ids)) onMessage(parsed)
    } catch {
      // ignore malformed frames; SSE keepalives don't fire onmessage anyway
    }
  }
  if (onError) es.onerror = onError
  return { close: () => es.close() }
}
