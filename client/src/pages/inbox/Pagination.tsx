export function Pagination({
  page, pageCount, onChange,
}: { page: number; pageCount: number; onChange: (n: number) => void }) {
  if (pageCount <= 1) return null
  return (
    <div style={{ display: 'flex', gap: 8, padding: 12, alignItems: 'center', justifyContent: 'center', fontSize: 13 }}>
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>prev</button>
      <span>page {page} of {pageCount}</span>
      <button disabled={page >= pageCount} onClick={() => onChange(page + 1)}>next</button>
    </div>
  )
}
