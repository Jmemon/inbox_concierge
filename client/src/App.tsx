import { AuthProvider, useAuth } from './auth/useAuth'
import Splash from './auth/Splash'
import Login from './auth/Login'
import Home from './pages/Home'

function Routes() {
  const { state } = useAuth()
  if (state.status === 'loading') return <Splash />
  if (state.status === 'anon') return <Login />
  return <Home />
}

export default function App() {
  return (
    <AuthProvider>
      <Routes />
    </AuthProvider>
  )
}
