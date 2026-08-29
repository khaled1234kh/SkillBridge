import React, { useEffect, useRef, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { Analysis, LearningItem, TutorMessage } from '../lib/types'
import { GapPill } from '../components/widgets'
import { IconChevron, IconChat, IconSend, IconAssessment } from './LearningIcons'

export default function LearningPage() {
  const { me } = useApp()
  const [studentId] = useState<number>(me?.student?.id ?? 0)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [items, setItems] = useState<LearningItem[]>([])
  const [openId, setOpenId] = useState<number | null>(null)
  const [generating, setGenerating] = useState<number | null>(null)

  const load = async () => {
    try {
      const [a, l] = await Promise.all([api.analysis(studentId), api.learning(studentId)])
      setAnalysis(a)
      setItems(l)
    } catch (e) {
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
    } finally {
      setGenerating(null)
    }
  }

  if (!studentId) return <div className="empty">Log in as a student to view your learning path.</div>

  const gapSkillIds = new Set((analysis?.skill_gaps || []).filter((g) => g.status !== 'strong').map((g) => g.skill_id))

  return (
    <div>
      <div className="card mb">
        <h3>My Learning Path</h3>
        <p className="card-sub">
          One personalized item per skill gap — each generated for your target role:{' '}
          <strong>{analysis?.role_title || 'none yet'}</strong>
        </p>
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
              />
            )
          })}
          {(analysis?.skill_gaps || []).filter((g) => g.status !== 'strong').length === 0 && (
            <div className="empty">No skill gaps — great! Or select a target role on Skills &amp; Roles to see your path.</div>
          )}
        </div>
      </div>
      <TutorPanel studentId={studentId} analysis={analysis} items={items} />
    </div>
  )
}

function LearningRow({ gap, item, open, generating, onToggle, onGenerate }: any) {
  return (
    <div className={`learning-item ${open ? 'open' : ''}`}>
      <div className="li-head" onClick={onToggle}>
        <IconChevron />
        <span className="li-title">{gap.skill_name}</span>
        <GapPill status={gap.status} />
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
            <section><h5>Explanation</h5><p>{item.explanation}</p></section>
            <section><h5>Practice exercise</h5><p>{item.practice_exercise}</p></section>
            <section><h5>Mini-project</h5><p>{item.mini_project}</p></section>
          </>
        )}
      </div>
    </div>
  )
}

function TutorPanel({ studentId, analysis, items }: { studentId: number; analysis: Analysis | null; items: LearningItem[] }) {
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

  const send = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || busy) return
    const text = input.trim()
    setInput('')
    setMessages((m) => [...m, { id: Date.now(), role: 'user', content: text, skill_id: skillId, created_at: '' }])
    setBusy(true)
    try {
      const reply = await api.tutorSend(studentId, text, skillId)
      setMessages((m) => [...m, reply])
    } catch {
      setMessages((m) => [...m, { id: Date.now(), role: 'assistant', content: '(Tutor unavailable — is the backend running?)', skill_id: skillId, created_at: '' }])
    } finally {
      setBusy(false)
    }
  }

  const skillOptions = items.length ? items : (analysis?.skill_gaps || []).filter((g) => g.status !== 'strong')

  return (
    <div className="card">
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><IconChat size={17} /> AI Tutor</h3>
      <p className="card-sub">Context-aware coaching — it knows your background, current gap, and target role.</p>
      <div className="tutor-layout">
        <div className="tutor-skill-list">
          <button className="ts-item" onClick={() => setSkillId(null)}>General</button>
          {skillOptions.map((g: any) => (
            <button
              key={g.skill_id ?? g.id}
              className={`ts-item ${skillId === g.skill_id ? 'active' : ''}`}
              onClick={() => setSkillId(g.skill_id ?? null)}
            >
              {g.skill_name ?? 'Skill'}
            </button>
          ))}
        </div>
        <div className="tutor-panel">
          <div className="tutor-header">
            {skillId ? (items.find((i) => i.skill_id === skillId)?.skill_name || 'Skill') : 'General coaching'}
          </div>
          <div className="tutor-messages" ref={scrollRef}>
            {messages.length === 0 && (
              <div className="muted small">
                Ask a question about your path. For example: "How should I approach learning Docker for an AI Engineer role?"
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}>{m.content}</div>
            ))}
            {busy && <div className="msg assistant">…</div>}
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
