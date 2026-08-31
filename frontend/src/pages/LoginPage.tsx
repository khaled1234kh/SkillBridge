import React, { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { GoogleConfig, UniversityOption } from '../lib/types'
import { IconUser, IconGoogle, IconShield, IconUniversity, IconCheck, IconAlert } from '../components/Icons'

type Mode = 'signin' | 'signup' | 'reset' | 'google-role' | 'google-demo'

export default function LoginPage() {
  const { login, signup } = useApp()
  const [mode, setMode] = useState<Mode>('signin')
  const [google, setGoogle] = useState<GoogleConfig | null>(null)
  const [verify, setVerify] = useState<{ token: string; status: 'pending' | 'ok' | 'error' } | null>(null)

  useEffect(() => {
    api.googleConfig().then(setGoogle).catch(() => {})
    const token = new URLSearchParams(window.location.search).get('token')
    if (token) {
      setVerify({ token, status: 'pending' })
      api.verifyEmail(token)
        .then(() => setVerify({ token, status: 'ok' }))
        .catch(() => setVerify({ token, status: 'error' }))
    }
  }, [])

  return (
    <div className="login-wrap">
      {verify && <VerifyBanner verify={verify} />}
      <AuthCard mode={mode} setMode={setMode} login={login} signup={signup} google={google} />
    </div>
  )
}

function VerifyBanner({ verify }: { verify: { token: string; status: 'pending' | 'ok' | 'error' } }) {
  if (verify.status === 'pending') {
    return <div className="info" style={{ maxWidth: 420, marginBottom: 12, justifyContent: 'center' }}><IconShield size={16} /> Verifying your email…</div>
  }
  if (verify.status === 'ok') {
    return <div className="info ok" style={{ maxWidth: 420, marginBottom: 12, justifyContent: 'center' }}><IconCheck size={16} /> Your email is verified. You can now sign in.</div>
  }
  return <div className="error" style={{ maxWidth: 420, marginBottom: 12, marginLeft: 'auto', marginRight: 'auto' }}>This verification link is invalid or has expired.</div>
}

function AuthCard({ mode, setMode, login, signup, google }: any) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('Student')
  const [university, setUniversity] = useState('')
  const [country, setCountry] = useState('')
  const [customUniversity, setCustomUniversity] = useState('')
  const [industry, setIndustry] = useState('')
  const [universities, setUniversities] = useState<UniversityOption[]>([])
  const [verifyNotice, setVerifyNotice] = useState('')
  const [pending, setPending] = useState<any>(null)
  const [resetToken, setResetToken] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.universities().then(setUniversities).catch(() => {})
  }, [])

  const switchMode = (m: Mode) => { setMode(m); setError(''); setInfo(''); setVerifyNotice('') }

  const selectedCountryUnis = () => {
    const g = universities.find((x) => x.country === country)
    return g ? g.universities : []
  }

  const doLogin = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(''); setBusy(true)
    try { await login(email.trim(), password) }
    catch (err: any) { setError(err.message || 'Login failed') }
    finally { setBusy(false) }
  }

  const doSignup = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(''); setVerifyNotice(''); setBusy(true)
    try {
      const uniChosen = role === 'Student' || role === 'University Admin'
      const uni = university === '__other__' ? customUniversity.trim() : university
      const res = await signup(email.trim(), password, displayName.trim(), role,
        uniChosen ? uni : undefined, uniChosen ? country : undefined, role === 'Company' ? industry.trim() : undefined)
      if (res.email_verified_delivery) {
        // SMTP is configured: the user must verify their email before using the account.
        setVerifyNotice(`A verification email was sent to ${email.trim()}. Please click the link in it to activate your account.`)
      }
    } catch (err: any) { setError(err.message || 'Sign-up failed') }
    finally { setBusy(false) }
  }

  const doResetRequest = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(''); setInfo(''); setBusy(true)
    try {
      const r = await api.resetRequest(email.trim())
      setInfo(r.message || 'Check your email for a reset link.')
      if (r.reset_token) setResetToken(r.reset_token)
      else setMode('reset')
    } catch (err: any) { setError(err.message) }
    finally { setBusy(false) }
  }

  const doResetConfirm = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(''); setBusy(true)
    try {
      await api.resetConfirm(resetToken.trim(), password)
      setInfo('Password updated. Sign in with your new password.')
      setMode('signin')
    } catch (err: any) { setError(err.message) }
    finally { setBusy(false) }
  }

  const doGoogle = async () => {
    setError('')
    if (google?.configured) { window.location.href = '/api/auth/google/login'; return }
    // demo identity provider
    setPending({ email: email.trim() || (displayName + '@demo.student.edu').toLowerCase() })
    switchMode('google-demo')
  }

  const doGoogleDemo = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(''); setBusy(true)
    try {
      const res = await api.googleDemo(pending?.email, displayName.trim() || 'Demo User')
      if (res.registered) { window.location.reload() }
      else { setPending(res); switchMode('google-role') }
    } catch (err: any) { setError(err.message) }
    finally { setBusy(false) }
  }

  const doGoogleRole = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(''); setBusy(true)
    try {
      await api.googleComplete(pending.google_sub, role)
      window.location.reload()
    } catch (err: any) { setError(err.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="card login-card">
      <div className="login-hero">
        <p className="eyebrow">Bridge university learning to real-world work</p>
        <h1>SkillBridge</h1>
        <p>One account for students, companies, and university administration.</p>
      </div>

      {(mode === 'signin' || mode === 'signup') && (
        <div className="tabs">
          <button className={mode === 'signin' ? 'active' : ''} onClick={() => switchMode('signin')}>Sign in</button>
          <button className={mode === 'signup' ? 'active' : ''} onClick={() => switchMode('signup')}>Create account</button>
        </div>
      )}

      {mode === 'signin' && (
        <form onSubmit={doLogin}>
          <div className="field"><label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com" /></div>
          <div className="field"><label>Password</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" /></div>
          {error && <div className="error">{error}</div>}
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
            <IconUser size={15} /> {busy ? 'Signing in…' : 'Sign in'}
          </button>
          <div className="login-links">
            <button type="button" className="link" onClick={() => switchMode('reset')}>Forgot password?</button>
          </div>
          <div className="divider" />
          <button type="button" className="btn btn-google" onClick={doGoogle}>
            <IconGoogle size={16} /> {google?.configured ? 'Continue with Google' : 'Continue with Google (demo)'}
          </button>
        </form>
      )}

      {mode === 'signup' && (
        <form onSubmit={doSignup}>
          <div className="field"><label>Full name</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} autoComplete="name" /></div>
          <div className="field"><label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
          <div className="field"><label>Password <span className="muted small">(8+ characters)</span></label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" /></div>
          <div className="field">
            <label>I am a…</label>
            <select value={role} onChange={(e) => { setRole(e.target.value); setCountry(''); setUniversity(''); setCustomUniversity('') }}>
              <option value="Student">Student seeking roles</option>
              <option value="Company">Company hiring talent</option>
              <option value="University Admin">University administration</option>
            </select>
          </div>
          {(role === 'Student' || role === 'University Admin') && (
            <div className="university-picker">
              <div className="field">
                <label>Country</label>
                <select value={country} onChange={(e) => { setCountry(e.target.value); setUniversity(''); setCustomUniversity('') }}>
                  <option value="">Select a country…</option>
                  {universities.map((u) => <option key={u.country} value={u.country}>{u.country}</option>)}
                </select>
              </div>
              {country && (
                <div className="field">
                  <label>University</label>
                  <select value={university} onChange={(e) => setUniversity(e.target.value)}>
                    <option value="">Select a university…</option>
                    {selectedCountryUnis().map((un) => <option key={un} value={un}>{un}</option>)}
                    <option value="__other__">Other (not listed)</option>
                  </select>
                </div>
              )}
              {country && university === '__other__' && (
                <div className="field">
                  <label>University name</label>
                  <input value={customUniversity} onChange={(e) => setCustomUniversity(e.target.value)} placeholder="Type your university…" />
                </div>
              )}
            </div>
          )}
          {role === 'Company' && (
            <div className="field"><label>Industry</label>
              <input value={industry} onChange={(e) => setIndustry(e.target.value)} placeholder="AI / Software" /></div>
          )}
          {verifyNotice && <div className="info" style={{ whiteSpace: 'normal' }}><IconShield size={15} /> {verifyNotice}</div>}
          {error && <div className="error">{error}</div>}
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
            {busy ? 'Creating account…' : 'Create account'}
          </button>
          <div className="login-links">
            <button type="button" className="link" onClick={() => switchMode('signin')}>Already have an account? Sign in</button>
          </div>
        </form>
      )}

      {mode === 'reset' && (
        <form onSubmit={resetToken ? doResetConfirm : doResetRequest}>
          <div className="field"><label>Email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
          {resetToken && (
            <>
              <div className="field"><label>New password</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" /></div>
              <div className="info"><IconShield size={15} /> Your reset token: <code>{resetToken.slice(0, 12)}…</code></div>
            </>
          )}
          {info && <div className="info">{info}</div>}
          {error && <div className="error">{error}</div>}
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
            {resetToken ? 'Set new password' : 'Send reset link'}
          </button>
          <div className="login-links">
            <button type="button" className="link" onClick={() => switchMode('signin')}>Back to sign in</button>
          </div>
        </form>
      )}

      {mode === 'google-demo' && (
        <form onSubmit={doGoogleDemo}>
          <div className="field"><label>Google account email</label>
            <input value={pending?.email || ''} onChange={(e) => setPending({ ...pending, email: e.target.value })} /></div>
          <div className="field"><label>Display name</label>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} /></div>
          {error && <div className="error">{error}</div>}
          <button className="btn btn-google" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
            <IconGoogle size={16} /> {busy ? 'Continuing…' : 'Continue with Google'}
          </button>
        </form>
      )}

      {mode === 'google-role' && (
        <form onSubmit={doGoogleRole}>
          <div className="info">You're new here — pick the account type for <strong>{pending?.email}</strong>.</div>
          <div className="field"><label>I am a…</label>
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="Student">Student seeking roles</option>
              <option value="Company">Company hiring talent</option>
              <option value="University Admin">University administration</option>
            </select>
          </div>
          {error && <div className="error">{error}</div>}
          <button className="btn btn-google" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
            <IconGoogle size={16} /> Create account
          </button>
          <div className="login-links">
            <button type="button" className="link" onClick={() => switchMode('signin')}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  )
}