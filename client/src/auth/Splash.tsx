export default function Splash() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 16, fontFamily: 'system-ui, sans-serif',
    }}>
      <div style={{ fontSize: 28, fontWeight: 600 }}>inbox concierge</div>
      <div style={{ fontSize: 14, color: '#666' }}>loading…</div>
    </div>
  )
}
