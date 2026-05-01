import { useEffect } from 'react'
import { useAuth } from '../auth/useAuth'
import { useInbox } from './inbox/useInbox'
import { useInboxSse } from './inbox/useInboxSse'
import { InboxList } from './inbox/InboxList'
import { Pagination } from './inbox/Pagination'
import { ReloadButton } from './inbox/ReloadButton'

export default function Home() {
  const { state, signOut } = useAuth()
  const inbox = useInbox()

  // Single render-time log capturing the most diagnostic state. Makes it
  // immediately clear in DevTools whether snapshot returned 0 threads (suspect)
  // vs whether the SSE event arrived but the merge didn't apply.
  console.log('[Home] render', {
    loading: inbox.loading,
    error: inbox.error,
    page: inbox.page,
    pageCount: inbox.pageCount,
    idLayerLen: inbox.idLayer.length,
    displayLayerLen: Object.keys(inbox.displayLayer).length,
    pageThreadsLen: inbox.pageThreads.length,
  })

  useInboxSse({
    onApply: inbox.applyThreadUpdates,
    snapshot: inbox.snapshot,
  })

  // Hydrate the current page when navigating to a page whose thread ids are
  // not yet in the display layer.
  useEffect(() => {
    void inbox.hydrateCurrentPage()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inbox.page])

  if (state.status !== 'authed') return null

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', minHeight: '100vh' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', borderBottom: '1px solid #eee',
      }}>
        <div style={{ fontWeight: 600 }}>inbox concierge</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <ReloadButton />
          <span style={{ fontSize: 14, color: '#444' }}>{state.user.name ?? state.user.email}</span>
          <button onClick={signOut} style={{ fontSize: 13, padding: '6px 10px' }}>sign out</button>
        </div>
      </header>
      <main>
        {inbox.error && <div style={{ color: '#8a1c25', padding: 16 }}>error: {inbox.error}</div>}
        {!inbox.error && inbox.loading && <div style={{ padding: 24 }}>loading…</div>}
        {!inbox.loading && <InboxList threads={inbox.pageThreads} />}
        <Pagination page={inbox.page} pageCount={inbox.pageCount} onChange={inbox.setPage} />
      </main>
    </div>
  )
}
