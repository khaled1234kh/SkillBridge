import React, { createContext, useContext, useEffect, useState } from 'react'
import { api } from './lib/api'
import type { Session, Analysis, Student, Company, RoleRecord } from './lib/types'

interface AppContextType {
  session: Session | null
  me: { role: string; display_name: string; entity_type: string; student?: Student; company?: Company; roles?: RoleRecord[]; analysis?: Analysis } | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshMe: () => Promise<void>
  refreshStudent: () => void
}

const AppContext = createContext<AppContextType>(null as any)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [me, setMe] = useState<any>(null)

  const refreshMe = async () => {
    if (session) {
      const data = await api.me(session.id)
      setMe(data)
    }
  }

  useEffect(() => {
    if (session) refreshMe()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session])

  const login = async (email: string, password: string) => {
    const s = await api.login(email, password)
    setSession(s)
  }

  const logout = () => {
    setSession(null)
    setMe(null)
  }

  const refreshStudent = () => refreshMe()

  return (
    <AppContext.Provider value={{ session, me, login, logout, refreshMe, refreshStudent }}>
      {children}
    </AppContext.Provider>
  )
}

export const useApp = () => useContext(AppContext)
