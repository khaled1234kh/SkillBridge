import React, { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { UniversityStatsResponse } from '../lib/types'
import { IconUniversity, IconAlert, IconCheck, IconVerified } from '../components/Icons'

export default function UniversityPage() {
  const [data, setData] = useState<UniversityStatsResponse | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.universityStats().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="card"><div className="error">{error}</div></div>
  if (!data) return <div className="card"><div className="loading">Loading aggregated statistics…</div></div>

  const ruleSatisfied = data.rule?.satisfied

  return (
    <div>
      <div className="rule-banner">
        <IconAlert size={17} style={{ color: 'var(--teal)' }} />
        <div>
          <strong>Privacy &amp; minimum-cohort rule.</strong> University admins see only anonymized,
          aggregated statistics — there is no path to an individual student's data. Statistics are
          only computed when the cohort has at least{' '}
          <strong>{data.rule?.min_cohort_size} students</strong>. Current cohort: {data.rule?.student_count}.
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <span className="label">Students in Cohort</span>
          <strong>{data.student_count ?? data.rule?.student_count ?? '–'}</strong>
          <small>{data.with_target_role ?? 0} with a target role</small>
        </div>
        <div className="stat-card">
          <span className="label">Average Match Score</span>
          <strong>{data.average_match_score != null ? Math.round(data.average_match_score) : '–'}%</strong>
          <small>Across the cohort</small>
        </div>
        <div className="stat-card">
          <span className="label">Verified Skills Earned</span>
          <strong>{data.verified_skills_total ?? 0}</strong>
          <small>{data.assessments_total ?? 0} assessment attempts logged</small>
        </div>
      </div>

      <div className="card">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <IconUniversity size={18} /> Recommended skill gaps across the cohort
        </h3>
        <p className="card-sub">Share of students who need improvement in each required skill (gap or missing).</p>
        {!ruleSatisfied ? (
          <div className="empty">
            Statistics hidden — cohort is below the minimum size of {data.rule?.min_cohort_size} students.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Skill</th>
                <th>Category</th>
                <th>Strong</th>
                <th>Gap</th>
                <th>Missing</th>
                <th>Need improvement</th>
              </tr>
            </thead>
            <tbody>
              {(data.skill_stats || []).map((s) => (
                <tr key={s.skill_name}>
                  <td style={{ fontWeight: 600 }}>{s.skill_name}</td>
                  <td className="muted">{s.category}</td>
                  <td>{s.strong}</td>
                  <td>{s.gap}</td>
                  <td>{s.missing}</td>
                  <td>
                    <div className="flex">
                      <div className="bar-wrap">
                        <div className="bar-fill" style={{ width: `${s.need_improvement_pct}%` }} />
                      </div>
                      <span className="small" style={{ minWidth: 48 }}>{s.need_improvement_pct}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="divider" />
        <div className="flex" style={{ gap: 18, color: 'var(--slate-500)', fontSize: 12.5, flexWrap: 'wrap' }}>
          <span><IconVerified size={14} style={{ color: 'var(--teal)' }} /> Verified skills are counted from passed assessments only.</span>
          <span>No individual student records are revealed at any point.</span>
        </div>
      </div>
    </div>
  )
}
