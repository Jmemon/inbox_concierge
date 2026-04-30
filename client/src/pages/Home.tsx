import { useEffect, useState } from 'react'
import { getJSON } from '../lib/api'
import { useAuth } from '../auth/useAuth'

type Profile = {
  email: string
  messages_total: number
  threads_total: number
  recent_subjects: string[]
}

export default function Home() {
  const { state, signOut } = useAuth()
  const [profile, setProfile] = useState<Profile | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getJSON<Profile>('/api/gmail/profile')
      .then((p) => { if (!cancelled) setProfile(p) })
      .catch((e) => { if (!cancelled) setError(String(e?.kind ?? e)) })
    return () => { cancelled = true }
  }, [])

  if (state.status !== 'authed') return null

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', minHeight: '100vh' }}>
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', borderBottom: '1px solid #eee',
      }}>
        <div style={{ fontWeight: 600 }}>inbox concierge</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 14, color: '#444' }}>{state.user.name ?? state.user.email}</span>
          <button onClick={signOut} style={{ fontSize: 13, padding: '6px 10px' }}>sign out</button>
        </div>
      </header>
      <main style={{ padding: 24, maxWidth: 720 }}>
        <h2 style={{ marginTop: 0 }}>backend gmail probe</h2>
        {error && <div style={{ color: '#8a1c25' }}>error: {error}</div>}
        {!error && !profile && <div>fetching…</div>}
        {profile && (
          <div>
            <div>email: <strong>{profile.email}</strong></div>
            <div>threads total: {profile.threads_total}</div>
            <div>messages total: {profile.messages_total}</div>
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600 }}>recent subjects</div>
              <ul>
                {profile.recent_subjects.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
