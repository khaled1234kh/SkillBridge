import React, { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { Analysis, ActivitySummary, Student, RoleRecord, Candidate, RoleSkillCoverage } from '../lib/types'
import { ScoreRing, GapPill, SkillTag, LevelBadge } from '../components/widgets'
import { IconArrowRight, IconCompany, IconRoles, IconCheck, IconVerified, IconFlame, IconBolt, IconLeaderboard, IconTrophy } from '../components/Icons'

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
  if (me.entity_type === 'student') return <StudentDashboard student={me.student} analysis={me.analysis ?? undefined} />
  if (me.entity_type === 'company') return <CompanyDashboard />
  return <UniversityDashboard />
}

function StudentDashboard({ student, analysis }: { student?: Student; analysis?: Analysis }) {
  const [activity, setActivity] = useState<ActivitySummary | null>(null)
  useEffect(() => {
    if (student) api.studentActivity(student.id).then(setActivity).catch(() => {})
  }, [student?.id])
  if (!student) return <div className="empty">No student profile linked to this account.</div>
  const gaps = analysis?.skill_gaps || []
  const strong = gaps.filter((g) => g.status === 'strong').length
  const gapCount = gaps.filter((g) => g.status !== 'strong').length
  const xpPct = activity ? Math.min(100, (activity.xp_into_level / activity.xp_per_level) * 100) : 0

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

      <div className="activity-card card mt" style={{ marginTop: 18 }}>
        <div className="act-head">
          <h3 style={{ margin: 0 }}>My Learning Activity</h3>
          <span className="act-lb">
            Level {activity?.level ?? '–'}
            <span className="act-level-bar"><span style={{ width: `${xpPct}%` }} /></span>
            <span className="small muted">{activity ? `${activity.xp_into_level}/${activity.xp_per_level} XP` : ''}</span>
          </span>
        </div>
        <div className="act-grid">
          <div className="act-tile">
            <div className="act-ico coral"><IconFlame size={20} /></div>
            <div><strong>{activity?.streak_days ?? '–'}-day streak</strong><small className="muted">Keep a login streak going</small></div>
          </div>
          <div className="act-tile">
            <div className="act-ico amber"><IconBolt size={20} /></div>
            <div><strong>{activity?.xp ?? '–'} XP</strong><small className="muted">{activity?.active_days ?? 0} active days</small></div>
          </div>
          <div className="act-tile">
            <div className="act-ico green"><IconTrophy size={20} /></div>
            <div><strong>{activity?.verified_skills ?? 0} verified</strong><small className="muted">{activity?.assessments_taken ?? 0} assessments taken</small></div>
          </div>
        </div>
        <div className="act-badges">
          {(activity?.badges || []).filter((b) => b.earned).slice(0, 6).map((b) => (
            <span className="badge-chip earned" key={b.code} title={b.desc}>{b.name}</span>
          ))}
          {(activity?.badges || []).filter((b) => !b.earned).slice(0, 3).map((b) => (
            <span className="badge-chip locked" key={b.code} title={b.hint || b.desc}>{b.name}</span>
          ))}
        </div>
        <div className="act-note small muted">
          <IconLeaderboard size={13} /> {activity?.leaderboard?.message || 'Cohort leaderboard'}
        </div>
      </div>
    </div>
  )
}

function CompanyDashboard() {
  const { me } = useApp()
  const [roles, setRoles] = useState<RoleRecord[]>([])
  const [candidates, setCandidates] = useState<Record<number, Candidate[]>>({})
  const [coverage, setCoverage] = useState<Record<number, RoleSkillCoverage>>({})

  useEffect(() => {
    api.roles().then((res) => setRoles(res.roles)).catch(() => {})
  }, [])

  useEffect(() => {
    roles.forEach((r) => {
      api.candidates(r.id).then((c) => setCandidates((prev) => ({ ...prev, [r.id]: c }))).catch(() => {})
      api.roleSkillCoverage(r.id).then((c) => setCoverage((prev) => ({ ...prev, [r.id]: c }))).catch(() => {})
    })
  }, [roles])

  const pool = Object.values(candidates).flat()
  const atLeast60 = pool.filter((c) => c.match_score >= 60).length

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
          <strong>{pool.length}</strong>
          <small>{atLeast60} at ≥60% match</small>
        </div>
        <div className="stat-card">
          <span className="label">Verified Skills Earned</span>
          <strong>{pool.reduce((s, c) => s + c.verified_count, 0)}</strong>
          <small>Across matched candidates</small>
        </div>
      </div>
      <div className="card">
        <h3>Your roles &amp; matching candidates</h3>
        {roles.length === 0 && <div className="empty">Define a role on the Skills &amp; Roles page to start matching.</div>}
        {roles.map((r) => {
          const list = candidates[r.id] || []
          const cov = coverage[r.id]
          const weakest = (cov?.skills || []).filter((s) => s.coverage_pct < 100).sort((a, b) => a.coverage_pct - b.coverage_pct)
          return (
            <div className="role-card" key={r.id} style={{ marginBottom: 10 }}>
              <div className="rc-head">
                <div>
                  <div className="rc-title">{r.title}</div>
                  <div className="rc-company">{r.company_name}</div>
                </div>
                <span className="muted small" style={{ marginTop: 2 }}>
                  {list.length} candidate{list.length === 1 ? '' : 's'} matched
                </span>
              </div>
              {cov && (
                <div className="coverage-block">
                  <div className="coverage-head">
                    <span className="small muted">Applicant skill coverage</span>
                    <span className="small muted">{cov.candidate_count} candidate{cov.candidate_count === 1 ? '' : 's'} · {weakest.length} skill{weakest.length === 1 ? '' : 's'} short</span>
                  </div>
                  {cov.skills.map((s) => (
                    <div className="cov-row" key={s.skill_id}>
                      <div className="cov-label">{s.skill_name} <span className="lv">{s.required_level}</span></div>
                      <div className="cov-track">
                        <div className="cov-fill" style={{ width: `${s.coverage_pct}%`, background: s.coverage_pct >= 60 ? 'var(--green)' : s.coverage_pct >= 30 ? 'var(--amber)' : 'var(--red)' }} />
                      </div>
                      <div className="cov-pct">{Math.round(s.coverage_pct)}%</div>
                      <div className="cov-tally small muted">
                        {s.strong} strong · {s.gap} gap · {s.missing} missing
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {list.length > 0 && (
                <div className="cand-list">
                  {list.map((c) => (
                    <div className="cand" key={c.student_id}>
                      <div>
                        <div className="cand-name">{c.name}</div>
                        <div className="cand-mail">{c.university}</div>
                      </div>
                      <div className="cand-right">
                        <span className="muted small">{c.verified_count} verified · {c.gap_count} gaps</span>
                        <ScoreInline value={c.match_score} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ScoreInline({ value }: { value: number }) {
  return (
    <span className="score-chip" style={{ color: value >= 60 ? 'var(--green)' : value >= 40 ? 'var(--amber)' : 'var(--red)' }}>
      {Math.round(value)}%
    </span>
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
