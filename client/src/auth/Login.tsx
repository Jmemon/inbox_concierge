function readAuthError(): string | null {
  const u = new URL(window.location.href)
  return u.searchParams.get('authError')
}

export default function Login() {
  const err = readAuthError()
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'system-ui, sans-serif',
    }}>
      <div style={{
        background: 'white', border: '1px solid #e5e5e5', borderRadius: 12, padding: 32,
        width: 360, boxShadow: '0 1px 3px rgba(0,0,0,0.06)', textAlign: 'center',
      }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>inbox concierge</h1>
        <p style={{ color: '#666', marginTop: 8, marginBottom: 24, fontSize: 14 }}>
          smart buckets for your gmail
        </p>
        {err && (
          <div style={{ background: '#fde7e9', color: '#8a1c25', padding: 8, borderRadius: 6, fontSize: 13, marginBottom: 12 }}>
            {err === 'denied' ? 'sign-in cancelled' : `sign-in failed (${err})`}
          </div>
        )}
        <button
          onClick={() => window.location.assign('/auth/login')}
          style={{
            width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #dadce0',
            background: 'white', cursor: 'pointer', fontSize: 14, fontWeight: 500,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
          }}
        >
          <span style={{ fontSize: 16 }}>G</span>
          sign in with google
        </button>
      </div>
    </div>
  )
}
