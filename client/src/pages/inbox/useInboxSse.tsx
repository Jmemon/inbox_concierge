import { useEffect, useRef } from 'react'
import { openInboxStream, type SseHandle, type ThreadIdsEvent } from '../../lib/sse'

/**
 * Lifecycle (homepage spec) — re-runs on every SSE reconnect:
 *   1. open SSE, buffer events without applying
 *   2. await snapshot()
 *   3. flush buffered events (applyThreadUpdates dedupes by internal_date)
 *   4. live events apply directly
 *
 * Why we re-run on reconnect: the api process unsubscribes from the user's
 * redis channel when the last SSE connection drops. Anything published during
 * the gap is lost (pubsub doesn't queue), so we must re-snapshot to close it.
 *
 * EventSource fires onerror on every blip — including the brief moment before
 * its own auto-reconnect succeeds. We rebuild the EventSource ourselves so
 * the snapshot+replay always pairs with a fresh server-side subscription.
 */
export function useInboxSse(opts: {
  onApply: (ids: string[]) => Promise<void> | void
  snapshot: () => Promise<void>
}): void {
  const buffer = useRef<ThreadIdsEvent[]>([])
  const ready = useRef(false)

  useEffect(() => {
    let cancelled = false
    let handle: SseHandle | null = null
    // Guard against re-entrant lifecycle() calls. EventSource can fire onerror
    // multiple times in quick succession; we only want one in-flight cycle.
    let cycling = false

    async function lifecycle() {
      if (cancelled || cycling) return
      cycling = true

      // Reset state for this cycle. Old handle (if any) was closed by the caller.
      buffer.current = []
      ready.current = false

      try {
        handle = openInboxStream(
          (ev) => {
            if (!ready.current) buffer.current.push(ev)
            else void opts.onApply(ev.thread_ids)
          },
          () => {
            // Connection blip. Close our handle and re-run the lifecycle.
            // The browser's own EventSource retry is bypassed in favor of
            // our own so each new connection pairs with snapshot+replay.
            if (cancelled) return
            handle?.close()
            handle = null
            // Allow another cycle to start. Schedule on a microtask so we
            // unwind the current onerror call stack first.
            cycling = false
            queueMicrotask(() => { void lifecycle() })
          },
        )

        await opts.snapshot()
        if (cancelled) return

        const flushed = buffer.current
        buffer.current = []
        ready.current = true
        for (const ev of flushed) {
          if (cancelled) return
          await opts.onApply(ev.thread_ids)
        }
      } finally {
        // cycling stays true while ready=true; reset only happens via the
        // onerror path above (which already toggles it before re-scheduling).
      }
    }

    void lifecycle()

    return () => {
      cancelled = true
      handle?.close()
      handle = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
