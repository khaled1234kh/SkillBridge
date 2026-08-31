import React, { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken } from './lib/api'
import type { Session } from './lib/types'

interface AppContextType {
  session: Session | null
  me: Session | null
  loading: boolean
  login: (email: string, password: string) => Promise<Session>
  signup: (email: string, password: string, display_name: string, role: string, university?: string, country?: string, industry?: string) => Promise<Session>
  logout: () => Promise<void>
  refreshMe: () => Promise<void>
  refreshStudent: () => void
}

const AppContext = createContext<AppContextType>(null as any)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshMe = async () => {
    if (getToken()) {
      const data = await api.me()
      setSession((prev) => ({ ...(prev || {}), ...data }))
    }
  }

  useEffect(() => {
    if (getToken()) {
      api.me()
        .then((data) => setSession((prev) => ({ ...(prev || {}), ...data })))
        .catch(() => setToken(null))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email: string, password: string) => {
    const s = await api.login(email, password)
    setSession(s)
    return s
  }

  const signup = async (email: string, password: string, display_name: string, role: string, university?: string, country?: string, industry?: string) => {
    const s = await api.signup(email, password, display_name, role, university, country, industry)
    const me = await api.me()
    setSession({ ...s, ...me })
    return { ...s, ...me }
  }

  const logout = async () => {
    try { await api.logout() } catch { /* best effort */ }
    setToken(null)
    setSession(null)
  }

  const refreshStudent = () => refreshMe()

  return (
    <AppContext.Provider value={{ session, me: session, loading, login, signup, logout, refreshMe, refreshStudent }}>
      {children}
    </AppContext.Provider>
  )
}

export const useApp = () => useContext(AppContext)