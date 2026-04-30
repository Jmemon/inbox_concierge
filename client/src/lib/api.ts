export type AuthError = 'unauthorized' | 'network'

export async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: 'same-origin' })
  if (r.status === 401) throw { kind: 'unauthorized' as const }
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return (await r.json()) as T
}

export async function postEmpty(url: string): Promise<void> {
  const r = await fetch(url, { method: 'POST', credentials: 'same-origin' })
  if (!r.ok && r.status !== 204) throw new Error(`${r.status} ${r.statusText}`)
}
