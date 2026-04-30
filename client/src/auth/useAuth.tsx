import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { getJSON, postEmpty } from '../lib/api'

export type Me = { id: string; email: string; name: string | null }

type AuthState =
  | { status: 'loading' }
  | { status: 'authed'; user: Me }
  | { status: 'anon' }

type Ctx = {
  state: AuthState
  refresh: () => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<Ctx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })

  const refresh = useCallback(async () => {
    try {
      const me = await getJSON<Me>('/auth/me')
      setState({ status: 'authed', user: me })
    } catch (e: any) {
      setState({ status: 'anon' })
    }
  }, [])

  const signOut = useCallback(async () => {
    await postEmpty('/auth/logout')
    setState({ status: 'anon' })
  }, [])

  useEffect(() => { void refresh() }, [refresh])

  return <AuthContext.Provider value={{ state, refresh, signOut }}>{children}</AuthContext.Provider>
}

export function useAuth(): Ctx {
  const v = useContext(AuthContext)
  if (!v) throw new Error('useAuth outside AuthProvider')
  return v
}
