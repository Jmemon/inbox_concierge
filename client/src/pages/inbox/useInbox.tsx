import { useCallback, useMemo, useRef, useState } from 'react'
import { getInbox, getThreadsBatch, type InboxThread } from '../../lib/api'

const PAGE_SIZE = 50
const SNAPSHOT_LIMIT = 200

type IdLayer = string[]
type DisplayLayer = Record<string, InboxThread>

export type UseInbox = {
  loading: boolean
  error: string | null
  asOf: number
  idLayer: IdLayer
  displayLayer: DisplayLayer
  page: number
  pageCount: number
  pageThreads: InboxThread[]
  setPage: (n: number) => void
  snapshot: () => Promise<void>
  applyThreadUpdates: (ids: string[]) => Promise<void>
  hydrateCurrentPage: () => Promise<void>
}

export function useInbox(): UseInbox {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [asOf, setAsOf] = useState<number>(0)
  const [idLayer, setIdLayer] = useState<IdLayer>([])
  const [displayLayer, setDisplayLayer] = useState<DisplayLayer>({})
  const [page, setPage] = useState(1)

  // Used to drop out-of-order GET /threads responses (per spec).
  const lastInternalDate = useRef<Record<string, number>>({})

  const snapshot = useCallback(async () => {
    console.log('[useInbox] snapshot starting')
    setLoading(true)
    setError(null)
    try {
      const resp = await getInbox({ limit: SNAPSHOT_LIMIT })
      console.log('[useInbox] snapshot result: thread count=', resp.threads.length, 'as_of=', resp.as_of)
      const order: string[] = []
      const display: DisplayLayer = {}
      for (const t of resp.threads) {
        order.push(t.id)
        display[t.id] = t
        if (t.recent_message) lastInternalDate.current[t.id] = t.recent_message.internal_date
      }
      setIdLayer(order)
      setDisplayLayer(display)
      setAsOf(resp.as_of)
    } catch (e: any) {
      console.error('[useInbox] snapshot error', e)
      setError(String(e?.kind ?? e?.message ?? e))
    } finally {
      setLoading(false)
    }
  }, [])

  const applyThreadUpdates = useCallback(async (ids: string[]) => {
    console.log('[useInbox] applyThreadUpdates entry id count=', ids.length)
    if (ids.length === 0) return
    let fetched: InboxThread[] = []
    try {
      fetched = await getThreadsBatch(ids)
    } catch (e) {
      // A failed batch is non-fatal: keep current state, surface to console.
      // The next SSE event or reload will re-attempt.
      console.error('[useInbox] batch fetch failed', e)
      return
    }

    // Pre-compute which threads are actually newer than what we have. Doing
    // this BEFORE the setState updaters keeps the updaters pure — the lastInt-
    // ernalDate ref is mutated exactly once per call, not once per strict-mode
    // re-run of the updater.
    const accepted: InboxThread[] = []
    const dropped: InboxThread[] = []
    for (const t of fetched) {
      const incoming = t.recent_message?.internal_date ?? 0
      const have = lastInternalDate.current[t.id] ?? 0
      if (incoming >= have) {
        accepted.push(t)
        if (t.recent_message) lastInternalDate.current[t.id] = incoming
      } else {
        dropped.push(t)
      }
    }
    console.log('[useInbox] applyThreadUpdates accepted=', accepted.length, 'dropped (out-of-order)=', dropped.length)
    if (accepted.length === 0) return

    setDisplayLayer((prev) => {
      const next = { ...prev }
      for (const t of accepted) next[t.id] = t
      return next
    })

    setIdLayer((prev) => {
      const merged = new Set(prev)
      for (const t of accepted) merged.add(t.id)
      // Re-sort by recent_message.internal_date desc; threads with no recent_message sink.
      const arr = [...merged]
      arr.sort((a, b) => {
        const da = lastInternalDate.current[a] ?? 0
        const db = lastInternalDate.current[b] ?? 0
        return db - da
      })
      console.log('[useInbox] applyThreadUpdates new idLayer length=', arr.length)
      return arr
    })
  }, [])

  const hydrateCurrentPage = useCallback(async () => {
    const start = (page - 1) * PAGE_SIZE
    const ids = idLayer.slice(start, start + PAGE_SIZE)
    const missing = ids.filter((id) => !(id in displayLayer))
    console.log('[useInbox] hydrateCurrentPage page=', page, 'missing=', missing.length)
    if (missing.length === 0) return
    await applyThreadUpdates(missing)
  }, [page, idLayer, displayLayer, applyThreadUpdates])

  const pageCount = Math.max(1, Math.ceil(idLayer.length / PAGE_SIZE))
  const pageThreads = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return idLayer.slice(start, start + PAGE_SIZE).map((id) => displayLayer[id]).filter(Boolean)
  }, [page, idLayer, displayLayer])

  return {
    loading, error, asOf,
    idLayer, displayLayer,
    page, pageCount, pageThreads,
    setPage,
    snapshot, applyThreadUpdates, hydrateCurrentPage,
  }
}
