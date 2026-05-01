import { useState } from 'react'
import { requestRefresh } from '../../lib/api'

/**
 * Triggers POST /api/inbox/refresh. The actual updated rows arrive via SSE
 * exactly the same way a beat-driven poll would — we just kick the server.
 *
 * We show a brief "syncing…" state for ~1.5s after the click so the user gets
 * tactile feedback even when nothing actually changed (no SSE event fires).
 */
export function ReloadButton() {
  const [busy, setBusy] = useState(false)

  async function onClick() {
    if (busy) return
    console.log('[ReloadButton] click fired')
    setBusy(true)
    try {
      await requestRefresh()
      console.log('[ReloadButton] requestRefresh → 202 ok')
    } catch (e) {
      // surface as a console error; don't block the UI
      console.error('[ReloadButton] requestRefresh failed', e)
    } finally {
      setTimeout(() => setBusy(false), 1500)
    }
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
