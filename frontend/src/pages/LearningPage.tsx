import React, { useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { Analysis, CareerRoadmap, LearningItem, Student, TutorMessage } from '../lib/types'
import { GapPill } from '../components/widgets'
import { IconChevron, IconChat, IconSend, IconAssessment, IconExternal, IconRoadmap, IconCheck } from '../components/Icons'

export default function LearningPage() {
  const { me, refreshStudent } = useApp()
  const studentId = me?.student?.id ?? 0
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [items, setItems] = useState<LearningItem[]>([])
  const [openId, setOpenId] = useState<number | null>(null)
  const [generating, setGenerating] = useState<number | null>(null)
  const [showTop, setShowTop] = useState(false)

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 600)
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('load', onScroll)
    return () => { window.removeEventListener('scroll', onScroll); window.removeEventListener('load', onScroll) }
  }, [])

  const load = async () => {
    try {
      const [a, l] = await Promise.all([api.analysis(studentId), api.learning(studentId)])
      setAnalysis(a)
      setItems(l)
    } catch {
      setItems([])
    }
  }
  useEffect(() => { if (studentId) load() }, [studentId])

  const generate = async (skillId: number) => {
    setGenerating(skillId)
    try {
      const item = await api.generateLearning(studentId, skillId)
      setItems((prev) => {
        const rest = prev.filter((i) => i.skill_id !== skillId)
        return [...rest, item]
      })
      if (openId !== skillId) setOpenId(skillId)
      await refreshStudent()
      await load()
    } finally {
      setGenerating(null)
    }
  }

  const toggleStep = async (item: LearningItem, n: number) => {
    const cur = new Set(item.progress ?? [])
    if (cur.has(n)) cur.delete(n); else cur.add(n)
    const steps = [...cur].sort((a, b) => a - b)
    try {
      const updated = await api.learningProgress(studentId, item.skill_id, steps)
      setItems((prev) => prev.map((i) => (i.skill_id === updated.skill_id ? updated : i)))
    } catch {
      /* keep local state unchanged if the save fails */
    }
  }

  if (!studentId) return <div className="empty">Log in as a student to view your learning path.</div>

  const gapSkillIds = new Set((analysis?.skill_gaps || []).filter((g) => g.status !== 'strong').map((g) => g.skill_id))
  const withRoadmap = items.filter((i) => i.roadmap?.steps?.length)
  const doneSteps = withRoadmap.reduce((s, i) => s + (i.progress?.length || 0), 0)
  const totalSteps = withRoadmap.reduce((s, i) => s + (i.roadmap?.steps.length || 0), 0)
  const overallPct = totalSteps ? Math.round((doneSteps / totalSteps) * 100) : 0

  return (
    <div>
      <div className="card mb">
        <h3>My Learning Path</h3>
        <p className="card-sub">
          One personalized item per skill gap — each generated for your target role:{' '}
          <strong>{analysis?.role_title || 'none yet'}</strong>
        </p>
        {withRoadmap.length > 0 && (
          <div className="overall-progress">
            <div className="op-row">
              <span className="small muted">Overall progress</span>
              <span className="small muted">{doneSteps}/{totalSteps} roadmap steps · {overallPct}%</span>
            </div>
            <div className="op-track"><div className="op-fill" style={{ width: `${overallPct}%` }} /></div>
          </div>
        )}
        <div className="legend">
          <span className="item"><GapPill status="gap" /> Needs practice</span>
          <span className="item"><GapPill status="missing" /> Not started</span>
        </div>
        <div>
          {(analysis?.skill_gaps || []).map((g) => {
            if (g.status === 'strong') return null
            const item = items.find((i) => i.skill_id === g.skill_id)
            return (
              <LearningRow
                key={g.skill_id}
                gap={g}
                item={item}
                open={openId === g.skill_id}
                generating={generating === g.skill_id}
                onToggle={() => setOpenId(openId === g.skill_id ? null : g.skill_id)}
                onGenerate={() => generate(g.skill_id)}
                onToggleStep={(n: number) => item && toggleStep(item, n)}
              />
            )
          })}
          {(analysis?.skill_gaps || []).filter((g) => g.status !== 'strong').length === 0 && (
            <div className="empty">No skill gaps — great! Or select a target role on Skills &amp; Roles to see your path.</div>
          )}
        </div>
      </div>
      <CareerRoadmapCard studentId={studentId} roleTitle={analysis?.role_title} />
      <ResourceCenter items={items} />
      {showTop && (
        <button className="btn back-top" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="Back to top">
          ↑ Back to top
        </button>
      )}
      <TutorPanel studentId={studentId} student={me?.student} items={items} />
    </div>
  )
}

function LearningRow({ gap, item, open, generating, onToggle, onGenerate, onToggleStep }: any) {
  const total = item?.roadmap?.steps?.length || 0
  const done = item?.progress?.length || 0
  return (
    <div className={`learning-item ${open ? 'open' : ''}`}>
      <div className="li-head" onClick={onToggle}>
        <IconChevron />
        <span className="li-title">{gap.skill_name}</span>
        <GapPill status={gap.status} />
        {total > 0 && (
          <span className={`step-progress ${done === total ? 'complete' : ''}`}>
            {done}/{total} steps
            <span className="sp-track"><span style={{ width: total ? `${(done / total) * 100}%` : 0 }} /></span>
          </span>
        )}
        <span className="muted small" style={{ marginLeft: 'auto' }}>
          Required: {gap.required_level}
          {gap.student_level ? ` · You: ${gap.student_level}` : ' · Not started'}
        </span>
      </div>
      <div className="li-body">
        {!item ? (
          <div className="flex" style={{ justifyContent: 'center', padding: 14 }}>
            <button className="btn btn-primary" onClick={onGenerate} disabled={generating}>
              <IconAssessment size={14} /> {generating ? 'Generating with AI…' : 'Generate learning content'}
            </button>
          </div>
        ) : (
          <>
            <section>
              <h5>Explanation</h5>
              <div className="md-body"><Markdown>{item.explanation}</Markdown></div>
            </section>
            <section>
              <h5>Practice exercise</h5>
              <div className="md-body"><Markdown>{item.practice_exercise}</Markdown></div>
            </section>
            <section>
              <h5>Mini-project</h5>
              <div className="md-body"><Markdown>{item.mini_project}</Markdown></div>
            </section>
            {item.resources && item.resources.length > 0 && (
              <section>
                <h5>Curated resources</h5>
                <div className="resource-list">
                  {item.resources.map((r: any, i: number) => (
                    <a key={i} className="resource" href={r.url} target="_blank" rel="noopener noreferrer">
                      <span className="resource-rank">{r.rank ?? i + 1}</span>
                      <span className="resource-main">
                        <span className="resource-title">{r.title}</span>
                        <span className="resource-meta">{r.type}{r.source ? ` · ${r.source}` : ''}{r.helpfulness ? ` · ${r.helpfulness}` : ''}</span>
                      </span>
                      <IconExternal size={15} />
                    </a>
                  ))}
                </div>
              </section>
            )}
            {item.roadmap && item.roadmap.steps.length > 0 && (
              <section>
                <h5 style={{ display: 'flex', alignItems: 'center', gap: 6 }}><IconRoadmap size={15} /> {item.roadmap.steps.length}-step roadmap</h5>
                <p className="small muted mb">{item.roadmap.summary}</p>
                <div className="roadmap">
                  {item.roadmap.steps.map((s: any, i: number) => {
                    const n = s.step ?? i + 1
                    const markDone = (item.progress || []).includes(n)
                    const sources = s.resources?.length
                      ? (s.resources as any[])
                      : ((s.resource_ranks || []) as number[])
                          .map((r: number) => item.resources?.[r - 1])
                          .filter(Boolean)
                    return (
                      <div className={`rm-step ${markDone ? 'done' : ''}`} key={i}>
                        <button
                          className={`rm-checkbox ${markDone ? 'checked' : ''}`}
                          onClick={() => onToggleStep(n)}
                          title={markDone ? 'Mark as not done' : 'Mark as done'}
                          aria-label={`Toggle step ${n}`}
                        >
                          {markDone ? <IconCheck size={13} /> : null}
                        </button>
                        <div className="rm-body">
                          <div className="rm-title">{s.title}</div>
                          <div className="rm-objective">{s.objective}</div>
                          {sources.length ? (
                            <div className="rm-links">
                              {sources.map((rc: any, j: number) => (
                                <a key={j} className="rm-link" href={rc.url} target="_blank" rel="noopener noreferrer">
                                  {rc.title}
                                </a>
                              ))}
                            </div>
                          ) : null}
                          <div className="rm-check">Checkpoint: {s.checkpoint}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function CareerRoadmapCard({ studentId, roleTitle }: { studentId: number; roleTitle?: string }) {
  const [map, setMap] = useState<CareerRoadmap | null>(null)
  const [openPhase, setOpenPhase] = useState<number | null>(1)

  useEffect(() => {
    let alive = true
    if (!studentId) return
    api.careerRoadmap(studentId).then((r) => { if (alive) setMap(r) }).catch(() => { if (alive) setMap(null) })
    return () => { alive = false }
  }, [studentId])

  if (!map || !map.phases.length) return null

  return (
    <div className="card mb cr-card">
      <div className="cr-head">
        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <IconRoadmap size={17} /> Career Roadmap
        </h3>
        <span className="muted small">{map.phase_count} phases · {map.role_title || roleTitle || 'your target role'}</span>
      </div>
      <p className="card-sub cr-sub">{map.summary}</p>
      <div className="cr-phases">
        {map.phases.map((p) => {
          const open = openPhase === p.phase
          const skillTxt = [...new Set(p.skills.map((s) => s.name))].join(', ')
          return (
            <div className={`cr-phase ${open ? 'open' : ''}`} key={p.phase}>
              <button className="cr-phase-head" onClick={() => setOpenPhase(open ? null : p.phase)}>
                <span className="cr-phase-num">{p.phase}</span>
                <span className="cr-phase-title">{p.title}</span>
                <span className="cr-phase-shift">{open ? '▲' : '▼'}</span>
              </button>
              {open && (
                <div className="cr-phase-body">
                  <p className="cr-goal">{p.goal}</p>
                  {skillTxt && (
                    <div className="cr-skills">
                      <span className="small muted">Develops:</span>
                      {[...new Set(p.skills.map((s) => s.name))].map((n) => (
                        <span className="chip-btn cr-chip" key={n}>{n}</span>
                      ))}
                    </div>
                  )}
                  <div className="cr-deliverables">
                    <div className="cr-deliverable-title">Deliverables</div>
                    {p.deliverables.map((d, i) => (
                      <div className="cr-deliverable" key={i}><span className="rm-checkbox" style={{ background: 'var(--navy)', borderColor: 'var(--navy)' }}>{i + 1}</span>
                        <div className="md-body"><Markdown>{d}</Markdown></div></div>
                    ))}
                  </div>
                  <div className="cr-check"><strong>Checkpoint:</strong> {p.checkpoint}</div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ResourceCenter({ items }: { items: LearningItem[] }) {
  const [mode, setMode] = useState<'combined' | 'per-skill'>('combined')
  const all = items.flatMap((i) =>
    (i.resources || []).map((r) => ({
      url: r.url, title: r.title, type: r.type, source: r.source, helpfulness: r.helpfulness,
      skillId: i.skill_id, skillName: i.skill_name,
    })),
  )
  if (!all.length) return null

  const byUrl = new Map<string, { url: string; title: string; type?: string; source?: string; helpfulness?: string; skills: Set<string>; times: number }>()
  all.forEach((r) => {
    const hit = byUrl.get(r.url)
    if (hit) {
      hit.skills.add(r.skillName)
      hit.times += 1
      if (r.helpfulness && !hit.helpfulness) hit.helpfulness = r.helpfulness
    } else {
      byUrl.set(r.url, { ...r, skills: new Set([r.skillName]), times: 1 })
    }
  })
  const unique = [...byUrl.values()].sort((a, b) => b.times - a.times || (a.helpfulness || '').localeCompare(b.helpfulness || ''))
  const skillCount = new Set(all.map((r) => r.skillName)).size

  const rowsFor = (list: typeof unique) =>
    list.map((r) => (
      <a key={r.url} className="resource" href={r.url} target="_blank" rel="noopener noreferrer">
        <span className="resource-rank">{r.times > 1 ? r.times : r.url?.slice(0, 1)}</span>
        <span className="resource-main">
          <span className="resource-title">{r.title}</span>
          <span className="resource-meta">{r.type}{r.source ? ` · ${r.source}` : ''}{r.helpfulness ? ` · ${r.helpfulness}` : ''}</span>
          {r.skills.size > 1 && <span className="rc-used">shared by {r.skills.size} skills: {[...r.skills].join(', ')}</span>}
        </span>
        <IconExternal size={15} />
      </a>
    ))

  const perSkill = new Map<string, typeof unique>()
  unique.forEach((r) => {
    const key = [...r.skills][0]
    perSkill.set(key, [...(perSkill.get(key) || []), r])
  })

  return (
    <div className="card mb rc-card">
      <div className="rc-head">
        <h3 style={{ margin: 0 }}>My Resources</h3>
        <span className="muted small">{unique.length} unique links across {skillCount} skills</span>
      </div>
      <p className="card-sub rc-sub">
        The same source is legitimately reused across skills — this center dedupes it, so you see every link exactly once.
      </p>
      <div className="rc-toggle">
        <button className={`rc-tab ${mode === 'combined' ? 'active' : ''}`} onClick={() => setMode('combined')}>Combined</button>
        <button className={`rc-tab ${mode === 'per-skill' ? 'active' : ''}`} onClick={() => setMode('per-skill')}>By skill</button>
      </div>
      {mode === 'combined' ? (
        <div className="resource-list">{rowsFor(unique)}</div>
      ) : (
        [...perSkill.entries()].map(([name, rows]) => (
          <div className="rc-skill" key={name}>
            <div className="rc-skill-name">{name}</div>
            <div className="resource-list">{rowsFor(rows)}</div>
          </div>
        ))
      )}
    </div>
  )
}

function TutorPanel({ studentId, student, items }: { studentId: number; student?: Student; items: LearningItem[] }) {
  const [messages, setMessages] = useState<TutorMessage[]>([])
  const [input, setInput] = useState('')
  const [skillId, setSkillId] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.tutorHistory(studentId).then(setMessages).catch(() => {})
  }, [studentId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages])

  const submitText = async (text: string, skill: number | null) => {
    if (!text.trim() || busy) return
    setMessages((m) => [...m, { id: Date.now(), role: 'user', content: text, skill_id: skill, created_at: '' }])
    setBusy(true)
    try {
      const reply = await api.tutorSend(studentId, text, skill)
      setMessages((m) => [...m, reply])
    } catch {
      setMessages((m) => [...m, { id: Date.now(), role: 'assistant', content: '(Tutor unavailable — is the backend running?)', skill_id: skill, created_at: '' }])
    } finally {
      setBusy(false)
    }
  }

  const send = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (busy) return
    const text = input.trim()
    setInput('')
    void submitText(text, skillId)
  }

  const skilled = new Map<number, string>()
  student?.self_reported_skills.forEach((s) => skilled.set(s.skill_id, s.name))
  student?.verified_skills.forEach((v) => skilled.set(v.skill_id, v.name))
  const skillCtx = [...skilled.values()]
  const contextLine = [
    student?.university ? `University: ${student.university}` : null,
    student?.target_role?.title ? `Target: ${student.target_role.title}` : null,
    skillCtx.length ? `Skills: ${skillCtx.slice(0, 3).join(', ')}${skillCtx.length > 3 ? '…' : ''}` : null,
  ].filter(Boolean).join(' · ')

  const EXAMPLES = ['Explain this skill simply', 'Quiz me on this skill', 'How should I practice this?']

  return (
    <div className="card">
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><IconChat size={17} /> AI Tutor</h3>
      <p className="card-sub">Context-aware coaching — it knows your background, current gap, and target role.</p>
      <div className="tutor-context">{contextLine}</div>
      <div className="tutor-layout">
        <div className="tutor-skill-list">
          <button className={`ts-item ${skillId === null ? 'active' : ''}`} onClick={() => setSkillId(null)}>General</button>
          {items.map((i) => (
            <button
              key={i.skill_id}
              className={`ts-item ${skillId === i.skill_id ? 'active' : ''}`}
              onClick={() => setSkillId(i.skill_id)}
            >
              {i.skill_name}
            </button>
          ))}
        </div>
        <div className="tutor-panel">
          <div className="tutor-header">
            {skillId ? items.find((i) => i.skill_id === skillId)?.skill_name || 'Skill' : 'General coaching'}
          </div>
          <div className="tutor-messages" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="muted small" style={{ padding: 8 }}>
                Ask a question about your path. For example: "How should I approach learning Docker for an AI Engineer role?"
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}><div className="md-body"><Markdown>{m.content}</Markdown></div></div>
            ))}
            {busy && <div className="msg assistant">…</div>}
          </div>
          <div className="tutor-examples">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="chip-btn" disabled={busy} onClick={() => { setInput(''); void submitText(ex, skillId) }}>
                {ex}
              </button>
            ))}
          </div>
          <form className="tutor-input" onSubmit={send}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask your AI tutor…" />
            <button type="submit" className="btn btn-primary" disabled={busy || !input.trim()}><IconSend size={15} /></button>
          </form>
        </div>
      </div>
    </div>
  )
}