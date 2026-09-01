import React from 'react'
import { AppProvider, useApp } from './AppContext'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import SkillsRolesPage from './pages/SkillsRolesPage'
import LearningPage from './pages/LearningPage'
import AssessmentsPage from './pages/AssessmentsPage'
import UniversityPage from './pages/UniversityPage'
import PublicProfilePage from './pages/PublicProfilePage'
import { IconDashboard, IconRoles, IconLearning, IconAssessment, IconUniversity, IconLogout } from './components/Icons'

type Section = 'dashboard' | 'skills' | 'learning' | 'assessments' | 'university'

function NotFound() {
  return (
    <div className="app-shell">
      <main className="content notfound-wrap">
        <div className="notfound">
          <div className="nf-code">404</div>
          <h1>Page not found</h1>
          <p>The page you're looking for doesn't exist or was moved.</p>
          <button className="btn btn-primary" onClick={() => { window.location.href = '/' }}>Back to SkillBridge</button>
        </div>
      </main>
    </div>
  )
}

function Shell() {
  const { session, me, logout } = useApp()
  const [section, setSection] = React.useState<Section>('dashboard')
  const [navOpen, setNavOpen] = React.useState(false)

  const titles: Record<Section, string> = {
    dashboard: 'Dashboard', skills: 'Skills & Roles', learning: 'Learning',
    assessments: 'Assessments', university: 'University Dashboard',
  }
  React.useEffect(() => {
    document.title = `${titles[section]} · SkillBridge`
  }, [section])

  if (!session) return <LoginPage />

  const role = session.role
  const nav: { key: Section; label: string; icon: React.ReactNode; show: boolean }[] = [
    { key: 'dashboard', label: 'Dashboard', icon: <IconDashboard size={18} />, show: true },
    { key: 'skills', label: 'Skills & Roles', icon: <IconRoles size={18} />, show: true },
    { key: 'learning', label: 'Learning', icon: <IconLearning size={18} />, show: role === 'Student' },
    { key: 'assessments', label: 'Assessments', icon: <IconAssessment size={18} />, show: role === 'Student' },
    { key: 'university', label: 'University Dashboard', icon: <IconUniversity size={18} />, show: role === 'University Admin' },
  ]
  const visibleNav = nav.filter((n) => n.show)
  if (!visibleNav.some((n) => n.key === section)) setSection(visibleNav[0]?.key || 'dashboard')

  const goTo = (key: Section) => { setSection(key); setNavOpen(false) }

  const roleLabel =
    role === 'Student'
      ? me?.student?.target_role ? `Target: ${me.student.target_role.title}` : 'Set your target role'
      : role === 'Company'
        ? me?.company ? `Hiring at ${me.company.name}` : 'Company account'
        : 'Administrator'
  const roleClass = role === 'Student' ? 'role-chip student' : role === 'Company' ? 'role-chip company' : 'role-chip university'

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className={`sidebar ${navOpen ? 'nav-open' : ''}`}>
        <div className="brand-block" onClick={() => goTo('dashboard')} role="button" tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') goTo('dashboard') }}>
          <div className="brand-mark">S</div>
          <div>
            <div className="eyebrow">Career Intelligence</div>
            <h1>SkillBridge</h1>
          </div>
        </div>
        <button className="nav-close" aria-label="Close menu" onClick={() => setNavOpen(false)}>✕</button>
        <nav className="main-nav">
          {visibleNav.map((n) => (
            <button key={n.key} className={`nav-item ${section === n.key ? 'active' : ''}`} onClick={() => goTo(n.key)}>
              {n.icon} {n.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-spacer" />
        <div className="role-badge">
          <div>
            <span className="rb-label">Signed in as</span>
            <strong style={{ fontSize: 12.5 }}>{me?.display_name || session.display_name}</strong>
            <div style={{ fontSize: 11, opacity: 0.7 }}>{session.role}</div>
          </div>
        </div>
      </aside>
      <div className="nav-backdrop" onClick={() => setNavOpen(false)} />
      <main className="content" id="main-content">
        <header className="topbar">
          <div>
            <button className="nav-toggle" aria-label="Open menu" onClick={() => setNavOpen(true)}>☰</button>
            <div>
              <p className="eyebrow">Verified skill loop</p>
              <h2>{titles[section]}</h2>
            </div>
          </div>
          <div className="topbar-actions">
            <span className={roleClass}>{roleLabel}</span>
            <button className="btn btn-ghost" onClick={logout}><IconLogout size={16} /> Log out</button>
          </div>
        </header>
        {section === 'dashboard' && <DashboardPage onNavigate={(s) => setSection(s as Section)} />}
        {section === 'skills' && <SkillsRolesPage />}
        {section === 'learning' && <LearningPage />}
        {section === 'assessments' && <AssessmentsPage />}
        {section === 'university' && <UniversityPage />}
        <footer className="app-footer">
          <span>SkillBridge · Career Intelligence Platform</span>
          <span>© {new Date().getFullYear()} SkillBridge. All rights reserved.</span>
        </footer>
      </main>
    </div>
  )
}

export default function App() {
  const m = window.location.pathname.match(/^\/p\/(\d+)/)
  if (m) return <PublicProfilePage studentId={Number(m[1])} />
  if (window.location.pathname.startsWith('/p/')) return <NotFound />
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  )
}
