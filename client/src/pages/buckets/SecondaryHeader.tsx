import type { Bucket } from '../../lib/api'
import { ReloadButton } from '../inbox/ReloadButton'
import { Pagination } from '../inbox/Pagination'
import { FilterByBucketDropdown } from './FilterByBucketDropdown'

export function SecondaryHeader({
  buckets, filterSelection, onFilterChange, onViewBuckets, onNewBucket,
  page, pageCount, extending, onPageChange,
}: {
  buckets: Bucket[]
  filterSelection: Set<string> | null
  onFilterChange: (next: Set<string> | null) => void
  onViewBuckets: () => void
  onNewBucket: () => void
  page: number
  pageCount: number
  extending: boolean
  onPageChange: (n: number) => void
}) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '8px 24px', borderBottom: '1px solid #eee', background: '#fafafa',
    }}>
      <ReloadButton />
      <FilterByBucketDropdown buckets={buckets} selection={filterSelection} onChange={onFilterChange} />
      <button onClick={onViewBuckets} style={{ fontSize: 13, padding: '6px 10px' }}>view buckets</button>
      <button onClick={onNewBucket} style={{ fontSize: 13, padding: '6px 10px' }}>new bucket</button>
      <div style={{ marginLeft: 'auto' }}>
        <Pagination page={page} pageCount={pageCount} extending={extending} onChange={onPageChange} />
      </div>
    </div>
  )
}
