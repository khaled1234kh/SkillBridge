import React, { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { GoogleConfig, UniversityOption } from '../lib/types'
import { IconUser, IconGoogle, IconShield, IconUniversity, IconCheck, IconAlert } from '../components/Icons'
import { PasswordInput, ToastRegion, useToast } from '../components/ui'

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
  const [fieldErrs, setFieldErrs] = useState<Record<string, string>>({})
  const toast = useToast()

  useEffect(() => {
    api.universities().then(setUniversities).catch(() => {})
  }, [])

  const switchMode = (m: Mode) => { setMode(m); setError(''); setInfo(''); setVerifyNotice(''); setFieldErrs({}) }

  const selectedCountryUnis = () => {
    const g = universities.find((x) => x.country === country)
    return g ? g.universities : []
  }

  const doLogin = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError('')
    const errs: Record<string, string> = {}
    if (!email.trim()) errs.email = 'Please enter your email.'
    if (!password) errs.password = 'Please enter your password.'
    setFieldErrs(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try { await login(email.trim(), password) }
    catch (err: any) { setError(err.message || 'Login failed') }
    finally { setBusy(false) }
  }

  const doSignup = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(''); setVerifyNotice('')
    const errs: Record<string, string> = {}
    if (!displayName.trim()) errs.displayName = 'Please enter your full name.'
    if (!/^\S+@\S+\.\S+$/.test(email.trim())) errs.email = 'Enter a valid email address.'
    if (password.length < 8) errs.password = 'Password must be at least 8 characters.'
    if (role === 'Company' && !industry.trim()) errs.industry = 'Please enter your industry.'
    setFieldErrs(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      const uniChosen = role === 'Student' || role === 'University Admin'
      const uni = university === '__other__' ? customUniversity.trim() : university
      const res = await signup(email.trim(), password, displayName.trim(), role,
        uniChosen ? uni : undefined, uniChosen ? country : undefined, role === 'Company' ? industry.trim() : undefined)
      toast.push('Account created successfully.', 'success')
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
      toast.push('Password updated successfully.', 'success')
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
    setError('')
    const errs: Record<string, string> = {}
    if ((role === 'Student' || role === 'University Admin') && !country) errs.country = 'Please choose a country.'
    if ((role === 'Student' || role === 'University Admin') && !university) errs.university = 'Please choose a university.'
    if (role === 'Company' && !industry.trim()) errs.industry = 'Please enter your industry.'
    setFieldErrs(errs)
    if (Object.keys(errs).length) return
    setBusy(true)
    try {
      const uni = university === '__other__' ? customUniversity.trim() : university
      await api.googleComplete(pending.google_sub, role, { university: uni, country, industry: industry.trim() })
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
        <form onSubmit={doLogin} noValidate>
          <div className={`field ${fieldErrs.email ? 'invalid' : ''}`}><label>Email</label>
            <input value={email} onChange={(e) => { setEmail(e.target.value); if (fieldErrs.email) setFieldErrs((f) => ({ ...f, email: '' })) }} autoComplete="email" placeholder="you@example.com" />
            {fieldErrs.email && <span className="field-err">{fieldErrs.email}</span>}</div>
          <div className={`field ${fieldErrs.password ? 'invalid' : ''}`}><label>Password</label>
            <PasswordInput value={password} onChange={(v) => { setPassword(v); if (fieldErrs.password) setFieldErrs((f) => ({ ...f, password: '' })) }} autoComplete="current-password" />
            {fieldErrs.password && <span className="field-err">{fieldErrs.password}</span>}</div>
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
        <form onSubmit={doSignup} noValidate>
          <div className={`field ${fieldErrs.displayName ? 'invalid' : ''}`}><label>Full name</label>
            <input value={displayName} onChange={(e) => { setDisplayName(e.target.value); if (fieldErrs.displayName) setFieldErrs((f) => ({ ...f, displayName: '' })) }} autoComplete="name" />
            {fieldErrs.displayName && <span className="field-err">{fieldErrs.displayName}</span>}</div>
          <div className={`field ${fieldErrs.email ? 'invalid' : ''}`}><label>Email</label>
            <input value={email} onChange={(e) => { setEmail(e.target.value); if (fieldErrs.email) setFieldErrs((f) => ({ ...f, email: '' })) }} autoComplete="email" />
            {fieldErrs.email && <span className="field-err">{fieldErrs.email}</span>}</div>
          <div className={`field ${fieldErrs.password ? 'invalid' : ''}`}><label>Password <span className="muted small">(8+ characters)</span></label>
            <PasswordInput value={password} onChange={(v) => { setPassword(v); if (fieldErrs.password) setFieldErrs((f) => ({ ...f, password: '' })) }} autoComplete="new-password" />
            {fieldErrs.password && <span className="field-err">{fieldErrs.password}</span>}</div>
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
            <div className={`field ${fieldErrs.industry ? 'invalid' : ''}`}><label>Industry</label>
              <input value={industry} onChange={(e) => { setIndustry(e.target.value); if (fieldErrs.industry) setFieldErrs((f) => ({ ...f, industry: '' })) }} placeholder="AI / Software" />
              {fieldErrs.industry && <span className="field-err">{fieldErrs.industry}</span>}</div>
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
                <PasswordInput value={password} onChange={setPassword} autoComplete="new-password" /></div>
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
        <form onSubmit={doGoogleRole} noValidate>
          <div className="info">You're new here — pick the account type for <strong>{pending?.email}</strong>.</div>
          <div className="field"><label>I am a…</label>
            <select value={role} onChange={(e) => { setRole(e.target.value); setCountry(''); setUniversity(''); setCustomUniversity(''); setIndustry('') }}>
              <option value="Student">Student seeking roles</option>
              <option value="Company">Company hiring talent</option>
              <option value="University Admin">University administration</option>
            </select>
          </div>
          {(role === 'Student' || role === 'University Admin') && (
            <div className="university-picker">
              <div className={`field ${fieldErrs.country ? 'invalid' : ''}`}>
                <label>Country</label>
                <select value={country} onChange={(e) => { setCountry(e.target.value); setUniversity(''); setCustomUniversity(''); if (fieldErrs.country) setFieldErrs((f) => ({ ...f, country: '' })) }}>
                  <option value="">Select a country…</option>
                  {universities.map((u) => <option key={u.country} value={u.country}>{u.country}</option>)}
                </select>
                {fieldErrs.country && <span className="field-err">{fieldErrs.country}</span>}
              </div>
              {country && (
                <div className={`field ${fieldErrs.university ? 'invalid' : ''}`}>
                  <label>University</label>
                  <select value={university} onChange={(e) => { setUniversity(e.target.value); if (fieldErrs.university) setFieldErrs((f) => ({ ...f, university: '' })) }}>
                    <option value="">Select a university…</option>
                    {selectedCountryUnis().map((un) => <option key={un} value={un}>{un}</option>)}
                    <option value="__other__">Other (not listed)</option>
                  </select>
                  {fieldErrs.university && <span className="field-err">{fieldErrs.university}</span>}
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
            <div className={`field ${fieldErrs.industry ? 'invalid' : ''}`}><label>Industry</label>
              <input value={industry} onChange={(e) => { setIndustry(e.target.value); if (fieldErrs.industry) setFieldErrs((f) => ({ ...f, industry: '' })) }} placeholder="AI / Software" />
              {fieldErrs.industry && <span className="field-err">{fieldErrs.industry}</span>}</div>
          )}
          {error && <div className="error">{error}</div>}
          <button className="btn btn-google" style={{ width: '100%', justifyContent: 'center' }} disabled={busy}>
            <IconGoogle size={16} /> Create account
          </button>
          <div className="login-links">
            <button type="button" className="link" onClick={() => switchMode('signin')}>Cancel</button>
          </div>
        </form>
      )}
      <ToastRegion toasts={toast.toasts} dismiss={toast.dismiss} />
    </div>
  )
}