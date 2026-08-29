import React, { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { Analysis, Student, RoleRecord } from '../lib/types'
import { ScoreRing, GapPill, SkillTag, LevelBadge } from '../components/widgets'
import { IconArrowRight, IconCompany, IconRoles, IconCheck, IconVerified } from '../components/Icons'

function nextStep(analysis: Analysis | undefined): string {
  if (!analysis) return 'Select a target role'
  if (analysis.gap_count === 0) return 'All requirements met — you are career ready!'
  const missing = analysis.skill_gaps.find((g) => g.status === 'missing')
  const gap = analysis.skill_gaps.find((g) => g.status === 'gap')
  const target = missing || gap
  return target ? target.skill_name : 'Take the next assessment'
}

export default function DashboardPage() {
  const { me } = useApp()
  if (!me) return null
  if (me.entity_type === 'student') return <StudentDashboard student={me.student} analysis={me.analysis} />
  if (me.entity_type === 'company') return <CompanyDashboard />
  return <UniversityDashboard />
}

function StudentDashboard({ student, analysis }: { student?: Student; analysis?: Analysis }) {
  if (!student) return <div className="empty">No student profile linked to this account.</div>
  const gaps = analysis?.skill_gaps || []
  const strong = gaps.filter((g) => g.status === 'strong').length
  const gapCount = gaps.filter((g) => g.status !== 'strong').length

  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card primary-tile">
          <span className="label">Career Readiness</span>
          <strong>{analysis ? Math.round(analysis.match_score) : '–'}%</strong>
          <small>Target: {analysis?.role_title || 'No target role set'}</small>
        </div>
        <div className="stat-card">
          <span className="label">Verified Skills</span>
          <strong>{student.verified_skills.length}</strong>
          <small>Earned via passed assessments</small>
        </div>
        <div className="stat-card">
          <span className="label">Recommended Next Step</span>
          <strong style={{ fontSize: 19, marginTop: 12 }}>{nextStep(analysis)}</strong>
          <small>{gapCount === 0 ? 'Career ready' : `${gapCount} skill gap${gapCount === 1 ? '' : 's'} to close`}</small>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3>Skill Gap Map</h3>
          <div className="legend">
            <span className="item"><GapPill status="strong" /> Strong</span>
            <span className="item"><GapPill status="gap" /> Gap</span>
            <span className="item"><GapPill status="missing" /> Missing</span>
          </div>
          <div className="stack">
            {gaps.length === 0 ? (
              <div className="empty">Select a target role on the Skills & Roles page to see your gap map.</div>
            ) : (
              gaps.map((g) => (
                <div className="skill-row" key={g.skill_id}>
                  <div>
                    <div className="sr-name">{g.skill_name}</div>
                    <div className="sr-cat">{g.category}</div>
                  </div>
                  <div className="sr-right">
                    {g.student_level ? <SkillTag name="" level={g.student_level} verified={g.verified} /> : null}
                    <GapPill status={g.status} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card">
          <h3>Job Match Score</h3>
          <p className="card-sub">How well your current skills match {analysis?.role_title || 'your target role'}</p>
          {analysis ? (
            <ScoreRing value={analysis.match_score} />
          ) : (
            <div className="empty">No target role selected.</div>
          )}
          <div className="divider" />
          <div className="flex between">
            <span className="muted small">{strong} skills covered</span>
            <span className="muted small">{gapCount} to improve</span>
          </div>
        </div>
      </div>

      <div className="card mt" style={{ marginTop: 18 }}>
        <h3>My Skill Profile</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {student.self_reported_skills.map((s) => (
            <SkillTag key={s.skill_id} name={s.name} level={s.level} verified={false} />
          ))}
          {student.verified_skills.map((s) => (
            <SkillTag key={s.skill_id} name={s.name} level={s.level} verified={true} />
          ))}
          {student.self_reported_skills.length === 0 && (
            <span className="muted small">Upload a CV to build your self-reported profile.</span>
          )}
        </div>
      </div>
    </div>
  )
}

function CompanyDashboard() {
  const { me } = useApp()
  const [roles, setRoles] = useState<RoleRecord[]>([])
  const [students, setStudents] = useState<Student[]>([])
  const [analysis, setAnalysis] = useState<Record<number, Analysis>>({})

  useEffect(() => {
    api.roles().then(setRoles)
    api.students().then(setStudents)
  }, [])

  useEffect(() => {
    students.forEach((s) => {
      if (s.target_role_id) {
        api.analysis(s.id).then((a) => setAnalysis((prev) => ({ ...prev, [s.id]: a }))).catch(() => {})
      }
    })
  }, [students])

  const roleCount = (roleId: number) =>
    students.filter((s) => s.target_role_id === roleId && (analysis[s.id]?.match_score ?? 0) >= 60).length

  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <span className="label">Posted Roles</span>
          <strong>{roles.length || '–'}</strong>
          <small>Active openings</small>
        </div>
        <div className="stat-card">
          <span className="label">Candidate Pool</span>
          <strong>{students.length}</strong>
          <small>Students in the cohort</small>
        </div>
      </div>
      <div className="card">
        <h3>Your roles &amp; matching candidates</h3>
        {roles.length === 0 && <div className="empty">Define a role on the Skills &amp; Roles page to start matching.</div>}
        {roles.map((r) => (
          <div className="role-card" key={r.id} style={{ marginBottom: 10 }}>
            <div className="rc-head">
              <div>
                <div className="rc-title">{r.title}</div>
                <div className="rc-company">{r.company_name}</div>
              </div>
              <span className="muted small" style={{ marginTop: 2 }}>
                {roleCount(r.id)} candidate{roleCount(r.id) === 1 ? '' : 's'} at ≥60% match
              </span>
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
              {r.required_skills.map((s) => (
                <span className="skill-tag" key={s.skill_id}>{s.name} <span className="lv">{s.required_level}</span></span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function UniversityDashboard() {
  const { refreshMe } = useApp()
  useEffect(() => { refreshMe() }, [])
  return (
    <div>
      <div className="stats-grid">
        <div className="stat-card">
          <span className="label">Students in Cohort</span>
          <strong>–</strong>
          <small>Aggregated across all programs</small>
        </div>
        <div className="stat-card">
          <span className="label">Average Match Score</span>
          <strong>–</strong>
          <small>vs. target roles</small>
        </div>
      </div>
      <div className="card">
        <h3>Cohort skill-gap overview</h3>
        <p className="card-sub">University admins see only anonymized, aggregated data.</p>
        <div className="empty">Select University Dashboard from the sidebar to load the full aggregated report.</div>
      </div>
    </div>
  )
}
