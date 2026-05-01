import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getInbox, getThreadsBatch, postInboxExtend, type Bucket, type InboxThread } from '../../lib/api'
import { subscribeSse } from '../../lib/sse'


const PAGE_SIZE = 50
const SNAPSHOT_LIMIT = 200
const UNCLASSIFIED = 'unclassified'

type IdLayer = string[]
type DisplayLayer = Record<string, InboxThread>


export function useInbox(opts: {
  buckets: Bucket[]
  filterSelection: Set<string> | null
}) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [idLayer, setIdLayer] = useState<IdLayer>([])
  const [displayLayer, setDisplayLayer] = useState<DisplayLayer>({})
  const [page, setPage] = useState(1)
  const [more, setMore] = useState<boolean | null>(null)
  const [extendInFlight, setExtendInFlight] = useState(false)

  const lastInternalDate = useRef<Record<string, number>>({})

  const snapshot = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const r = await getInbox({ limit: SNAPSHOT_LIMIT })
      const order: string[] = []
      const display: DisplayLayer = {}
      for (const t of r.threads) {
        order.push(t.id); display[t.id] = t
        if (t.recent_message) lastInternalDate.current[t.id] = t.recent_message.internal_date
      }
      setIdLayer(order); setDisplayLayer(display)
    } catch (e: any) { setError(String(e?.kind ?? e?.message ?? e)) }
    finally { setLoading(false) }
  }, [])

  const applyThreadUpdates = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return
    let fetched: InboxThread[] = []
    try { fetched = await getThreadsBatch(ids) } catch { return }
    const accepted: InboxThread[] = []
    for (const t of fetched) {
      const incoming = t.recent_message?.internal_date ?? 0
      const have = lastInternalDate.current[t.id] ?? 0
      if (incoming >= have) {
        accepted.push(t)
        if (t.recent_message) lastInternalDate.current[t.id] = incoming
      }
    }
    if (accepted.length === 0) return
    setDisplayLayer(prev => { const n = { ...prev }; for (const t of accepted) n[t.id] = t; return n })
    setIdLayer(prev => {
      const merged = new Set(prev); for (const t of accepted) merged.add(t.id)
      return [...merged].sort((a, b) =>
        (lastInternalDate.current[b] ?? 0) - (lastInternalDate.current[a] ?? 0))
    })
  }, [])

  // Subscribe to extend_complete to update `more` and hydrate the new ids.
  useEffect(() => {
    return subscribeSse((e) => {
      if (e.event !== 'extend_complete') return
      setMore(e.more)
      setExtendInFlight(false)
      void applyThreadUpdates(e.thread_ids)
    })
  }, [applyThreadUpdates])

  const requestExtend = useCallback(async () => {
    if (extendInFlight || more === false) return
    if (idLayer.length === 0) return
    let smallest = Number.MAX_SAFE_INTEGER
    for (const id of idLayer) {
      const t = displayLayer[id]
      const d = t?.recent_message?.internal_date
      if (d && d < smallest) smallest = d
    }
    if (smallest === Number.MAX_SAFE_INTEGER) return
    setExtendInFlight(true)
    try { await postInboxExtend(smallest) }
    catch { setExtendInFlight(false) }
  }, [extendInFlight, more, idLayer, displayLayer])

  // Filtered id layer: walk idLayer in order, keep only ids whose displayLayer
  // row's resolved bucket key matches the active filter set.
  const filteredIdLayer = useMemo(() => {
    if (!opts.filterSelection) return idLayer
    const activeIds = new Set(opts.buckets.map(b => b.id))
    const sel = opts.filterSelection
    return idLayer.filter((id) => {
      const t = displayLayer[id]
      if (!t) return false
      const bid = t.bucket_id
      const key = (bid === null || !activeIds.has(bid)) ? UNCLASSIFIED : bid
      return sel.has(key)
    })
  }, [idLayer, displayLayer, opts.filterSelection, opts.buckets])

  const pageCount = Math.max(1, Math.ceil(filteredIdLayer.length / PAGE_SIZE))
  const pageThreads = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return filteredIdLayer.slice(start, start + PAGE_SIZE)
      .map(id => displayLayer[id]).filter(Boolean)
  }, [page, filteredIdLayer, displayLayer])

  // Auto-extend trigger: when on the last page and it's partial, AND server
  // hasn't told us we're at the bottom of inbox history.
  useEffect(() => {
    if (more === false || extendInFlight) return
    const start = (page - 1) * PAGE_SIZE
    const remaining = filteredIdLayer.length - start
    if (remaining < PAGE_SIZE && !opts.filterSelection) {
      // Only auto-extend when no filter active (filter could artificially shrink the page).
      void requestExtend()
    }
  }, [page, filteredIdLayer.length, more, extendInFlight, opts.filterSelection, requestExtend])

  const hydrateCurrentPage = useCallback(async () => {
    const start = (page - 1) * PAGE_SIZE
    const ids = idLayer.slice(start, start + PAGE_SIZE)
    const missing = ids.filter(id => !(id in displayLayer))
    if (missing.length > 0) await applyThreadUpdates(missing)
  }, [page, idLayer, displayLayer, applyThreadUpdates])

  return {
    loading, error, idLayer, displayLayer, page, pageCount, pageThreads,
    setPage, snapshot, applyThreadUpdates, hydrateCurrentPage,
    more, requestExtend,
  }
}
