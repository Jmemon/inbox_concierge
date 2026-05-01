import { useState } from 'react'
import { requestRefresh } from '../../lib/api'

/**
 * Triggers POST /api/inbox/refresh AND a client-side resync in parallel.
 *
 * The 202 path kicks the worker for a Gmail poll (its results arrive later via
 * SSE, identical to a beat-driven poll). The resync immediately re-fetches
 * /api/inbox so the display layer reflects current Postgres state right away —
 * without this the user can click reload and see nothing change when the Gmail
 * poll yields no history records (silent return path in poll_new_messages).
 *
 * Resync is reload-only on purpose: scheduled (beat) polls keep their quieter
 * SSE-only update path so background refreshes don't churn the UI.
 *
 * We show a brief "syncing…" state for ~1.5s after the click so the user gets
 * tactile feedback even when nothing actually changed.
 */
export function ReloadButton({ onResync }: { onResync: () => Promise<void> }) {
  const [busy, setBusy] = useState(false)

  async function onClick() {
    if (busy) return
    console.log('[ReloadButton] click fired')
    setBusy(true)
    // Fire both in parallel: requestRefresh is a 202 fire-and-forget kick, and
    // onResync is an independent canonical-state pull. Order doesn't matter.
    const refreshP = requestRefresh().then(
      () => console.log('[ReloadButton] requestRefresh → 202 ok'),
      (e) => console.error('[ReloadButton] requestRefresh failed', e),
    )
    const resyncP = onResync().catch((e) =>
      console.error('[ReloadButton] resync failed', e),
    )
    try { await Promise.all([refreshP, resyncP]) }
    finally { setTimeout(() => setBusy(false), 1500) }
  }

  return (
    <button
      onClick={onClick}
      disabled={busy}
      style={{ fontSize: 13, padding: '6px 10px' }}
      aria-label="reload inbox"
    >
      {busy ? 'syncing…' : 'reload'}
    </button>
  )
}
