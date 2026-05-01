// Compact pagination row meant to live inside a flex parent (e.g. the
// SecondaryHeader). No outer padding/centering — the parent controls placement.
// Returns null only when there's a single page AND no extend is running, so a
// tiny inbox still surfaces the "loading more…" hint while we prefetch.
export function Pagination({
  page, pageCount, extending, onChange,
}: {
  page: number
  pageCount: number
  extending: boolean
  onChange: (n: number) => void
}) {
  if (pageCount <= 1 && !extending) return null
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 13 }}>
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>prev</button>
      <span>page {page} of {pageCount}</span>
      {extending && <span style={{ color: '#888', fontStyle: 'italic' }}>loading more…</span>}
      <button disabled={page >= pageCount} onClick={() => onChange(page + 1)}>next</button>
    </div>
  )
}
