import React, { useEffect, useRef, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { Analysis, AssessmentAttempt, IntegrityFlag, QuizQuestion } from '../lib/types'
import { GapPill } from '../components/widgets'
import { IconAssessment, IconAlert, IconFlag, IconCheck } from '../components/Icons'

export default function AssessmentsPage() {
  const { me, refreshStudent } = useApp()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [attempts, setAttempts] = useState<AssessmentAttempt[]>([])

  useEffect(() => {
    if (me?.student?.id) {
      api.analysis(me.student.id).then(setAnalysis).catch(() => {})
      api.studentAssessments(me.student.id).then(setAttempts).catch(() => {})
    }
  }, [me])

  if (!me?.student) return <div className="empty">Log in as a student to take assessments.</div>
  const viableSkills = (analysis?.skill_gaps || []).filter((g) => g.status !== 'strong')

  return (
    <div className="grid grid-2">
      <div className="card">
        <h3>Verify a skill</h3>
        <p className="card-sub">Take a proctored assessment to move a skill from self-reported to Verified.</p>
        {viableSkills.length === 0 && (
          <div className="empty">No skill gaps to assess. Select a target role first.</div>
        )}
        <div className="stack">
          {viableSkills.map((g) => (
            <AssessmentStarter key={g.skill_id} gap={g} onDone={() => { refreshStudent(); api.analysis(me.student!.id).then(setAnalysis); api.studentAssessments(me.student!.id).then(setAttempts) }} />
          ))}
        </div>
      </div>
      <div className="card">
        <h3>Assessment history</h3>
        {attempts.length === 0 && <div className="empty">No attempts recorded yet.</div>}
        <div className="stack">
          {attempts.map((a) => (
            <div className="role-card" key={a.id}>
              <div className="flex between">
                <strong>{a.skill_name}</strong>
                <span className={`pill ${a.passed ? 'strong' : 'missing'}`}>{a.passed ? 'Passed' : 'Failed'}</span>
              </div>
              <p className="small muted" style={{ marginTop: 6 }}>
                Score {a.score}% · {a.level_before} → {a.level_after}
              </p>
              {a.flags && JSON.parse(a.flags).length > 0 && (
                <p className="small" style={{ color: 'var(--amber)' }}><IconFlag size={13} /> Integrity flags raised on this attempt</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function AssessmentStarter({ gap, onDone }: { gap: any; onDone: () => void }) {
  const { me } = useApp()
  const [active, setActive] = useState(false)
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [answers, setAnswers] = useState<string[]>([])
  const [tabSwitches, setTabSwitches] = useState(0)
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState(false)
  const startRef = useRef<number>(0)

  const start = async () => {
    setGenerating(true)
    setResult(null)
    setTabSwitches(0)
    setAnswers([])
    try {
      const res = await api.generateAssessment(me!.student!.id, gap.skill_id)
      setQuestions(res.questions)
      setAnswers(new Array(res.questions.length).fill(''))
      startRef.current = Date.now()
      setActive(true)
    } catch (e: any) {
      alert('Failed to generate quiz: ' + e.message)
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    if (!active) return
    const onVis = () => {
      if (document.hidden) setTabSwitches((n) => n + 1)
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [active])

  const setAnswer = (i: number, v: string) => setAnswers((prev) => prev.map((x, idx) => (idx === i ? v : x)))

  const submit = async () => {
    setBusy(true)
    const freeText = questions.map((q, i) => (q.type === 'free_text' ? answers[i] || '' : '')).filter((x) => x)
    try {
      const res = await api.submitAssessment(me!.student!.id, {
        skill_id: gap.skill_id,
        questions,
        answers,
        total_seconds: Math.round((Date.now() - startRef.current) / 1000),
        tab_switches: tabSwitches,
        free_text_answers: freeText,
      })
      setResult(res)
      setActive(false)
      onDone()
    } catch (e: any) {
      alert('Submit failed: ' + e.message)
    } finally {
      setBusy(false)
    }
  }

  if (generating) return <div className="loading">Generating assessment questions with AI…</div>

  if (active && questions.length) {
    return (
      <div className="learning-item open" style={{ border: '1.5px solid var(--teal)' }}>
        <div className="li-body" style={{ display: 'block', padding: 16 }}>
          <div className={`integrity-bar ${tabSwitches > 0 ? 'flagged' : ''}`} style={{ marginBottom: 14 }}>
            <span className="dot" />
            <span className="ib-text">
              {tabSwitches > 0
                ? `${tabSwitches} tab-switch${tabSwitches === 1 ? '' : 'es'} detected — this is logged as an integrity flag.`
                : 'Proctored by SkillBridge. Do not switch tabs — that raises an integrity flag.'}
            </span>
          </div>
          <h4 style={{ marginBottom: 12 }}>Assessment: {gap.skill_name}</h4>
          {questions.map((q, i) => (
            <div className="question-block" key={i}>
              <div className="q-text">{i + 1}. {q.question}</div>
              {q.type === 'multiple_choice' ? (
                q.options.map((opt) => (
                  <button key={opt} className={`mc-option ${answers[i] === opt ? 'selected' : ''}`} onClick={() => setAnswer(i, opt)}>
                    <span className="radio" /> {opt}
                  </button>
                ))
              ) : (
                <textarea className="free-text" value={answers[i]} onChange={(e) => setAnswer(i, e.target.value)}
                  placeholder="Type your answer… (pasted polished/AI-style text may be flagged)" />
              )}
            </div>
          ))}
          <div className="flex" style={{ justifyContent: 'flex-end' }}>
            <button className="btn" onClick={() => setActive(false)}>Cancel</button>
            <button className="btn btn-primary" onClick={submit} disabled={busy}><IconCheck size={15} /> {busy ? 'Submitting…' : 'Submit assessment'}</button>
          </div>
        </div>
      </div>
    )
  }

  if (result) {
    return (
      <div className="learning-item open" style={{ border: `1.5px solid ${result.passed ? 'var(--green)' : 'var(--red)'}` }}>
        <div className="li-body" style={{ display: 'block', padding: 18 }}>
          <div className="result-summary">
            <div className={`result-score ${result.passed ? 'pass' : 'fail'}`}>{Math.round(result.score)}%</div>
            <h4>{result.passed ? `Verified: you passed ${gap.skill_name}!` : `Not passed — keep learning ${gap.skill_name}`}</h4>
            <p className="muted small mb">Proficiency {result.level_before} → {result.level_after}</p>
            <button className="btn" onClick={() => setResult(null)}>Back to skill list</button>
          </div>
          {result.flags.length > 0 && (
            <div>
              <h5 className="small" style={{ textTransform: 'uppercase', letterSpacing: 0.06, color: 'var(--amber)', marginBottom: 6 }}>
                Integrity flags raised
              </h5>
              {result.flags.map((f: IntegrityFlag, i: number) => (
                <div className="flag-item" key={i}>
                  <IconAlert size={16} />
                  <div className="flag-body">
                    <div className="fl-label">{f.label}</div>
                    <div className="fl-detail">{f.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
          {result.flags.length === 0 && (
            <p className="muted small" style={{ marginTop: 8 }}>No integrity concerns on this attempt.</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="role-card">
      <div className="flex between">
        <div>
          <strong>{gap.skill_name}</strong>
          <div className="small muted">Required: {gap.required_level}</div>
        </div>
        <button className="btn btn-primary btn-sm" onClick={start}><IconAssessment size={14} /> Start assessment</button>
      </div>
    </div>
  )
}
