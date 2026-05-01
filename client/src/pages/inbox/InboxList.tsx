import type { InboxThread } from '../../lib/api'

function abbreviate(addr: string | null | undefined): string {
  if (!addr) return '?'
  // "Alice Smith <alice@x.com>" → "Alice Smith"; bare email → username before @
  const m = addr.match(/^([^<]+)<.*?>$/)
  const name = (m ? m[1] : addr).trim()
  if (name.includes('@')) return name.split('@')[0]
  return name
}

export function InboxList({ threads }: { threads: InboxThread[] }) {
  if (threads.length === 0) {
    return <div style={{ padding: 24, color: '#666' }}>syncing your inbox…</div>
  }
  return (
    <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
      {threads.map((t) => {
        const from = abbreviate(t.recent_message?.from ?? null)
        const preview = t.recent_message?.body_preview ?? ''
        return (
          <li
            key={t.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '160px 1fr 2fr',
              gap: 16,
              padding: '10px 16px',
              borderBottom: '1px solid #eee',
              fontSize: 14,
              alignItems: 'baseline',
            }}
          >
            <div style={{ color: '#222', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{from}</div>
            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.subject || '(no subject)'}</div>
            <div style={{ color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{preview}</div>
          </li>
        )
      })}
    </ul>
  )
}
