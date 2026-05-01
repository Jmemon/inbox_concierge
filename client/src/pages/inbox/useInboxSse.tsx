import { useEffect, useRef } from 'react'
import { subscribeSse } from '../../lib/sse'


export function useInboxSse(opts: {
  onApply: (ids: string[]) => Promise<void> | void
  snapshot: () => Promise<void>
}): void {
  const buffer = useRef<string[][]>([])
  const ready = useRef(false)

  useEffect(() => {
    let cancelled = false

    async function runLifecycle() {
      buffer.current = []
      ready.current = false
      try {
        await opts.snapshot()
        if (cancelled) return
        const flushed = buffer.current
        buffer.current = []
        ready.current = true
        for (const ids of flushed) {
          if (cancelled) return
          await opts.onApply(ids)
        }
      } catch (e) {
        console.error('[useInboxSse] snapshot failed', e)
      }
    }

    const unsub = subscribeSse((e) => {
      if (e.event === '_open') void runLifecycle()
      else if (e.event === '_error') ready.current = false
      else if (e.event === 'threads_updated') {
        if (!ready.current) buffer.current.push(e.thread_ids)
        else void opts.onApply(e.thread_ids)
      }
    })

    return () => { cancelled = true; unsub() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
}
