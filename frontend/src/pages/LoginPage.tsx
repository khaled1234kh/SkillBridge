import React, { useState } from 'react'
import { useApp } from '../AppContext'
import { IconUser, IconLogout } from '../components/Icons'

const QUICK_ACCOUNTS = [
  { name: 'Aisha Rahman', email: 'aisha@student.edu', role: 'Student' },
  { name: 'Omar Haddad', email: 'omar@student.edu', role: 'Student' },
  { name: 'Northstar Labs', email: 'hr@northstar.com', role: 'Company' },
  { name: 'Signal Works', email: 'hr@signal.com', role: 'Company' },
  { name: 'University Analytics', email: 'admin@univ.edu', role: 'University Admin' },
]

export default function LoginPage() {
  const { login } = useApp()
  const [email, setEmail] = useState('aisha@student.edu')
  const [password, setPassword] = useState('demo1234')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const doLogin = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email.trim(), password)
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="card login-card">
        <div className="login-hero">
          <p className="eyebrow">Bridge university learning to real-world work</p>
          <h1>Sign in to SkillBridge</h1>
          <p>One account for students, companies, and university administration.</p>
        </div>
        <form onSubmit={doLogin}>
          <div className="field">
            <label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          {error && <div className="error">{error}</div>}
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
            <IconUser size={15} /> {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <div className="login-quick">
          <h4>Demo accounts — one click</h4>
          <div className="quick-grid">
            {QUICK_ACCOUNTS.map((a) => (
              <button key={a.email} className="quick-account" onClick={() => { setEmail(a.email); setPassword('demo1234'); doLogin() }}>
                <span className="qa-name">{a.name}</span>
                <span className="qa-role">{a.role}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
