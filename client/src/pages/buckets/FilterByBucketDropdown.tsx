import { useState } from 'react'
import type { Bucket } from '../../lib/api'

const UNCLASSIFIED = 'unclassified'

export function FilterByBucketDropdown({ buckets, selection, onChange }: {
  buckets: Bucket[]
  selection: Set<string> | null
  onChange: (next: Set<string> | null) => void
}) {
  const [open, setOpen] = useState(false)
  const all = new Set([...buckets.map(b => b.id), UNCLASSIFIED])
  const effective = selection ?? all
  const allSelected = !selection
  const summary = allSelected ? 'all buckets' : `${effective.size} selected`

  function toggle(key: string) {
    const next = new Set(effective)
    next.has(key) ? next.delete(key) : next.add(key)
    onChange(next.size === all.size && [...next].every(k => all.has(k)) ? null : next)
  }

  function toggleAll() {
    onChange(allSelected ? new Set() : null)
  }

  return (
    <div style={{ position: 'relative' }}>
      <button onClick={() => setOpen(o => !o)} style={{ fontSize: 13, padding: '6px 10px' }}>
        filter: {summary} ▾
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 4,
          background: '#fff', border: '1px solid #ddd', borderRadius: 4,
          padding: 8, minWidth: 220, zIndex: 10,
        }}>
          <button
            onClick={toggleAll}
            style={{
              width: '100%', textAlign: 'left', fontSize: 12,
              padding: '4px 6px', marginBottom: 4,
              background: 'transparent', border: '1px solid #eee', borderRadius: 3,
              cursor: 'pointer',
            }}
          >
            {allSelected ? 'deselect all' : 'select all'}
          </button>
          {[...buckets, { id: UNCLASSIFIED, name: 'unclassified', is_default: false } as any].map(b => (
            <label key={b.id} style={{ display: 'flex', gap: 8, padding: '4px 0', fontSize: 13 }}>
              <input type="checkbox" checked={effective.has(b.id)} onChange={() => toggle(b.id)} />
              <span>{b.name}{b.is_default ? '' : ''}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
