import React, { useEffect, useRef, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { Analysis, AssessmentAttempt, IntegrityFlag, QuizQuestion } from '../lib/types'
import { GapPill } from '../components/widgets'
import { IconAssessment, IconAlert, IconFlag, IconCheck, IconTrophy, IconClock } from '../components/Icons'

export default function AssessmentsPage() {
  const { me, refreshStudent } = useApp()
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [attempts, setAttempts] = useState<AssessmentAttempt[]>([])
  const [keepIds, setKeepIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    if (me?.student?.id) {
      api.analysis(me.student.id).then(setAnalysis).catch(() => {})
      api.studentAssessments(me.student.id).then(setAttempts).catch(() => {})
    }
  }, [me])

  if (!me?.student) return <div className="empty">Log in as a student to take assessments.</div>
  const viableSkills = (analysis?.skill_gaps || []).filter((g) => g.status !== 'strong')
  const allGaps = analysis?.skill_gaps || []
  const renderedGaps = allGaps.filter((g) => g.status !== 'strong' || keepIds.has(g.skill_id))
  const keep = (id: number) => setKeepIds((prev) => { const n = new Set(prev); n.add(id); return n })
  const release = (id: number) => setKeepIds((prev) => { const n = new Set(prev); n.delete(id); return n })

  return (
    <div className="grid grid-2">
      <div className="card">
        <h3>Verify a skill</h3>
        <p className="card-sub">Take a proctored 10-question assessment to move a skill from self-reported to Verified.</p>
        {viableSkills.length === 0 && !keepIds.size && (
          <div className="empty">No skill gaps to assess. Select a target role first.</div>
        )}
        <div className="stack">
          {renderedGaps.map((g) => {
            const last = attempts.filter((a) => a.skill_id === g.skill_id).sort((a, b) => b.id - a.id)[0]
            return (
              <AssessmentStarter
                key={g.skill_id}
                gap={g}
                lastAttempt={last}
                onActivate={() => keep(g.skill_id)}
                onDeactivate={() => release(g.skill_id)}
                onDone={() => { refreshStudent(); api.analysis(me.student!.id).then(setAnalysis); api.studentAssessments(me.student!.id).then(setAttempts) }}
              />
            )
          })}
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

type Mode = 'idle' | 'quiz' | 'practice' | 'result'

function AssessmentStarter({ gap, lastAttempt, onDone, onActivate, onDeactivate }: { gap: any; lastAttempt?: AssessmentAttempt; onDone: () => void; onActivate: () => void; onDeactivate: () => void }) {
  const { me } = useApp()
  const [mode, setMode] = useState<Mode>('idle')
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [answers, setAnswers] = useState<string[]>([])
  const [tabSwitches, setTabSwitches] = useState(0)
  const [result, setResult] = useState<any>(null)
  const [practiceData, setPracticeData] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [current, setCurrent] = useState(0)
  const [locked, setLocked] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef<number>(0)

  const start = async (practice: boolean) => {
    setGenerating(true)
    setResult(null)
    setPracticeData(null)
    setTabSwitches(0)
    setAnswers([])
    setCurrent(0)
    setLocked(false)
    setElapsed(0)
    onActivate()
    try {
      const res = await api.generateAssessment(me!.student!.id, gap.skill_id, { practice })
      if (practice && res.previous_score !== null) {
        setPracticeData(res)
        setMode('practice')
      } else {
        setQuestions(res.questions)
        setAnswers(new Array(res.questions.length).fill(''))
        startRef.current = Date.now()
        setMode('quiz')
      }
    } catch (e: any) {
      alert('Failed to generate quiz: ' + e.message)
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    if (mode !== 'quiz') return
    const onVis = () => {
      if (document.hidden) setTabSwitches((n) => n + 1)
    }
    const onBlur = () => setTabSwitches((n) => n + 1)
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('blur', onBlur)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('blur', onBlur)
    }
  }, [mode])

  useEffect(() => {
    if (mode !== 'quiz' || locked) return
    const t = window.setInterval(() => setElapsed((e) => e + 1), 1000)
    return () => window.clearInterval(t)
  }, [mode, locked, current])

  const setAnswer = (i: number, v: string) => setAnswers((prev) => prev.map((x, idx) => (idx === i ? v : x)))

  const selectOption = (opt: string) => {
    if (locked) return
    setAnswer(current, opt)
    setLocked(true)
  }
  const lockFreeText = () => { if (!answers[current]?.trim()) return; setLocked(true) }
  const next = () => {
    if (current + 1 < questions.length) { setCurrent((c) => c + 1); setLocked(false) }
    else submit()
  }

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
      setQuestions([])
      setCurrent(0)
      setLocked(false)
      setMode('result')
      onDone()
    } catch (e: any) {
      alert('Submit failed: ' + e.message)
    } finally {
      setBusy(false)
    }
  }

  if (generating) return <div className="loading">Generating assessment questions with AI…</div>

  if (mode === 'practice' && practiceData) {
    return (
      <div className="learning-item open" style={{ border: '1.5px solid var(--teal)' }}>
        <div className="li-body" style={{ display: 'block', padding: 16 }}>
          <h4 style={{ marginBottom: 6 }}>Practice review: {gap.skill_name}</h4>
          <p className="small muted mb">
            These are the questions from your last attempt — score {practiceData.previous_score}%,{' '}
            {practiceData.previous_passed ? 'passed' : 'not passed'}. This mode doesn't affect your Verified profile.
          </p>
          {practiceData.previous_results.map((r: any) => {
            const q = practiceData.questions[r.index]
            return (
              <div className="question-block" key={r.index}>
                <div className="flex between">
                  <div className="q-text">{r.index + 1}. {q.question}</div>
                  <span className={`pill ${r.correct ? 'strong' : 'missing'}`} style={{ flexShrink: 0 }}>{r.correct ? 'Correct' : 'Incorrect'}</span>
                </div>
                {q.type === 'multiple_choice'
                  ? q.options.map((opt: string) => (
                      <div key={opt} className={`mc-option read-only ${opt === q.answer ? 'is-answer' : ''} ${opt === r.answer ? 'is-taken' : ''}`}>
                        <span className="radio" /> {opt}{opt === q.answer ? ' ✓' : ''}
                      </div>
                    ))
                  : <div className="free-text read-only">Your answer: {r.answer || '(empty)'}</div>}
                <div className="q-expl"><IconTrophy size={14} /> {q.explanation}</div>
              </div>
            )
          })}
          <div className="flex" style={{ justifyContent: 'flex-end' }}>
            <button className="btn" onClick={() => { setMode('idle'); onDeactivate() }}>Back</button>
            <button className="btn btn-primary" onClick={() => start(false)}><IconAssessment size={14} /> Redo for real</button>
          </div>
        </div>
      </div>
    )
  }

  if (mode === 'quiz' && questions.length) {
    const q = questions[current]
    const isLast = current === questions.length - 1
    const chosen = answers[current] || ''
    const isCorrect = q?.type === 'multiple_choice' && chosen && q.answer && chosen.trim().toLowerCase() === q.answer.trim().toLowerCase()
    const progressPct = ((current + (locked ? 1 : 0)) / questions.length) * 100
    const mm = String(Math.floor(elapsed / 60)).padStart(2, '0')
    const ss = String(elapsed % 60).padStart(2, '0')
    return (
      <div className="learning-item open" style={{ border: '1.5px solid var(--teal)' }}>
        <div className="li-body" style={{ display: 'block', padding: 16 }}>
          <div className="quiz-top">
            <div className="quiz-progress-wrap">
              <div className="quiz-head">
                <span className="quiz-count">Question {current + 1} of {questions.length}</span>
                <span className="quiz-timer"><IconClock size={14} /> {mm}:{ss}</span>
              </div>
              <div className="quiz-progress"><div className="quiz-progress-fill" style={{ width: `${progressPct}%` }} /></div>
            </div>
            <div className={`integrity-bar ${tabSwitches > 0 ? 'flagged' : ''}`} style={{ marginBottom: 0 }}>
              <span className="dot" />
              <span className="ib-text">
                {tabSwitches > 0
                  ? `${tabSwitches} tab-switch${tabSwitches === 1 ? '' : 'es'} detected — this is logged as an integrity flag.`
                  : 'Proctored. Don\'t switch tabs — that raises an integrity flag.'}
              </span>
            </div>
          </div>
          <div className={`question-block ${locked ? 'has-feedback' : ''}`} key={current}>
            <div className="q-text">{current + 1}. {q.question}</div>
            {q.type === 'multiple_choice' ? (
              q.options.map((opt) => {
                let cls = 'mc-option'
                if (locked) {
                  if (opt === q.answer) cls += ' is-answer'
                  else if (opt === chosen) cls += ' is-taken'
                  else cls += ' read-only'
                } else if (chosen === opt) cls += ' selected'
                return (
                  <button key={opt} className={cls} disabled={locked} onClick={() => selectOption(opt)}>
                    <span className="radio" /> {opt}{locked && !chosen && opt === q.answer ? ' ✓ correct' : ''}
                  </button>
                )
              })
            ) : (
              <textarea className="free-text" value={answers[current]} disabled={locked}
                onChange={(e) => setAnswer(current, e.target.value)}
                placeholder="Type your answer… (pasted polished/AI-style text may be flagged)" />
            )}
            {locked && (
              <div className={`inline-feedback ${isLast ? '' : 'mf'}`}>
                {q.type === 'multiple_choice' ? (
                  <div className={`fb-banner ${isCorrect ? 'correct' : 'wrong'}`}>
                    <span className="dot" /> {isCorrect ? 'Correct!' : 'Not quite.'} <span className="fb-answer">Answer: <strong>{q.answer}</strong></span>
                  </div>
                ) : (
                  <div className="fb-banner neutral">
                    <span className="dot" /> Compare your answer with the model response below.
                  </div>
                )}
                <div className="q-expl" style={{ marginTop: 8 }}><IconTrophy size={14} /> {q.explanation}</div>
                {q.type === 'free_text' && <div className="model-answer">Model answer: <strong>{q.answer}</strong></div>}
              </div>
            )}
          </div>
          <div className="flex" style={{ justifyContent: 'flex-end' }}>
            <button className="btn" onClick={() => { setMode('idle'); onDeactivate() }}>Cancel</button>
            {!locked && q.type !== 'free_text' ? (
              <button className="btn btn-primary" disabled><IconCheck size={15} /> Select an answer</button>
            ) : !locked ? (
              <button className="btn btn-primary" onClick={lockFreeText} disabled={!chosen.trim()}><IconCheck size={15} /> Check answer</button>
            ) : (
              <button className="btn btn-primary" onClick={next} disabled={busy}>
                {isLast ? (busy ? 'Submitting…' : 'Submit assessment') : `Next question ›`}
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  if (mode === 'result' && result) {
    return (
      <div className="learning-item open" style={{ border: `1.5px solid ${result.passed ? 'var(--green)' : 'var(--red)'}` }}>
        <div className="li-body" style={{ display: 'block', padding: 18 }}>
          <div className="result-summary">
            <div className={`result-score ${result.passed ? 'pass' : 'fail'}`}>{Math.round(result.score)}%</div>
            <h4>{result.passed ? `Verified: you passed ${gap.skill_name}!` : `Not passed — keep learning ${gap.skill_name}`}</h4>
            <p className="muted small mb">Proficiency {result.level_before} → {result.level_after}</p>
            <div className="flex" style={{ gap: 8 }}>
              <button className="btn" onClick={() => { setMode('idle'); onDeactivate() }}>Back to skill list</button>
              {lastAttempt && <button className="btn" onClick={() => start(true)}><IconTrophy size={14} /> Practice review</button>}
            </div>
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
          <div style={{ marginTop: 14 }}>
            <h5 className="small" style={{ textTransform: 'uppercase', letterSpacing: 0.06, marginBottom: 6 }}>Question review</h5>
            {result.questions.map((q: QuizQuestion, i: number) => {
              const r = result.per_question[i]
              return (
                <div className="question-block" key={i}>
                  <div className="flex between">
                    <div className="q-text">{i + 1}. {q.question}</div>
                    <span className={`pill ${r.correct ? 'strong' : 'missing'}`} style={{ flexShrink: 0 }}>{r.correct ? 'Correct' : 'Incorrect'}</span>
                  </div>
                  {q.type === 'multiple_choice'
                    ? q.options.map((opt: string) => (
                        <div key={opt} className={`mc-option read-only ${opt === q.answer ? 'is-answer' : ''} ${opt === r.answer ? 'is-taken' : ''}`}>
                          <span className="radio" /> {opt}{opt === q.answer ? ' ✓ correct' : ''}
                        </div>
                      ))
                    : <div className="free-text read-only">Your answer: {(r.answer as string) || '(empty)'}</div>}
                  <div className="q-expl"><IconTrophy size={14} /> {q.explanation}</div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="role-card">
      <div className="flex between">
        <div>
          <strong>{gap.skill_name}</strong>
          <div className="small muted">Required: {gap.required_level}{lastAttempt ? ` · last score ${lastAttempt.score}%` : ''}</div>
        </div>
        <div className="flex" style={{ gap: 6 }}>
          {lastAttempt && (
            <button className="btn btn-sm" onClick={() => start(true)}><IconTrophy size={14} /> Practice</button>
          )}
          <button className="btn btn-primary btn-sm" onClick={() => start(false)}><IconAssessment size={14} /> Start assessment</button>
        </div>
      </div>
    </div>
  )
}