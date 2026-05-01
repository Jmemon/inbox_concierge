import { useEffect, useState } from 'react'
import { useAuth } from '../auth/useAuth'
import { useInbox } from './inbox/useInbox'
import { useInboxSse } from './inbox/useInboxSse'
import { InboxList } from './inbox/InboxList'
import { useBuckets } from './buckets/useBuckets'
import { SecondaryHeader } from './buckets/SecondaryHeader'
import { ViewBucketsModal } from './buckets/ViewBucketsModal'
import { NewBucketModal } from './buckets/NewBucketModal'


export default function Home() {
  const { state, signOut } = useAuth()
  const { buckets, byId: bucketsById, rename, softDelete } = useBuckets()
  const [filterSelection, setFilterSelection] = useState<Set<string> | null>(null)
  const [showView, setShowView] = useState(false)
  const [showNew, setShowNew] = useState(false)

  const inbox = useInbox({ buckets, filterSelection })
  useInboxSse({ onApply: inbox.applyThreadUpdates, snapshot: inbox.snapshot })

  // Hydrate the current page when navigating to a page whose thread ids are
  // not yet in the display layer.
  useEffect(() => { void inbox.hydrateCurrentPage() /* eslint-disable-next-line */ }, [inbox.page])

  if (state.status !== 'authed') return null

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', minHeight: '100vh' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', borderBottom: '1px solid #eee',
      }}>
        <div style={{ fontWeight: 600 }}>inbox concierge</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 14, color: '#444' }}>{state.user.name ?? state.user.email}</span>
          <button onClick={signOut} style={{ fontSize: 13, padding: '6px 10px' }}>sign out</button>
        </div>
      </header>

      {/* SecondaryHeader owns the reload button, filter dropdown, bucket controls,
          and (right-aligned) the pagination row for the inbox list. */}
      <SecondaryHeader
        buckets={buckets} filterSelection={filterSelection}
        onFilterChange={setFilterSelection}
        onViewBuckets={() => setShowView(true)}
        onNewBucket={() => setShowNew(true)}
        page={inbox.page} pageCount={inbox.pageCount}
        extending={inbox.extendInFlight} onPageChange={inbox.setPage}
      />

      <main>
        {inbox.error && <div style={{ color: '#8a1c25', padding: 16 }}>error: {inbox.error}</div>}
        {!inbox.error && inbox.loading && <div style={{ padding: 24 }}>loading…</div>}
        {!inbox.loading && <InboxList threads={inbox.pageThreads} bucketsById={bucketsById} />}
        {inbox.more === false && (
          <div style={{ padding: 12, fontSize: 12, color: '#888', textAlign: 'center' }}>
            (end of inbox history)
          </div>
        )}
      </main>

      {showView && <ViewBucketsModal buckets={buckets} onClose={() => setShowView(false)}
                                       onRename={rename} onDelete={softDelete} />}
      {showNew && <NewBucketModal onClose={() => setShowNew(false)} />}
    </div>
  )
}
