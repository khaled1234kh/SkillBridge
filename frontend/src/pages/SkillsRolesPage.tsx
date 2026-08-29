import React, { useEffect, useState } from 'react'
import { useApp } from '../AppContext'
import { api } from '../lib/api'
import type { RoleRecord, Student, Skill } from '../lib/types'
import { IconPlus, IconEdit, IconTrash, IconUpload, IconSearch, IconRoles, IconCheck } from '../components/Icons'
import { LevelBadge, SkillTag } from '../components/widgets'

const LEVELS = ['Beginner', 'Intermediate', 'Advanced']

export default function SkillsRolesPage() {
  const { me } = useApp()
  if (!me) return null
  if (me.entity_type === 'student') return <StudentBrowse student={me.student} />
  if (me.entity_type === 'company') return <CompanyRoles company={me.company} />
  return <ReadOnlyBrowse />
}

function useRolesStudents() {
  const [roles, setRoles] = useState<RoleRecord[]>([])
  const [skills, setSkills] = useState<Skill[]>([])
  useEffect(() => {
    api.roles().then(setRoles)
    api.skills().then(setSkills)
  }, [])
  return { roles, setRoles, skills }
}

// ------------------------------------------------------------------ Student browse
function StudentBrowse({ student }: { student?: Student }) {
  const { refreshStudent } = useApp()
  const { roles, skills } = useRolesStudents()
  const [q, setQ] = useState('')
  const [selectedRole, setSelectedRole] = useState<number | null>(student?.target_role_id ?? null)
  const [uploading, setUploading] = useState(false)
  const [cvMsg, setCvMsg] = useState('')

  const filtered = roles.filter(
    (r) =>
      r.title.toLowerCase().includes(q.toLowerCase()) ||
      (r.company_name || '').toLowerCase().includes(q.toLowerCase()),
  )

  const chooseTarget = async (roleId: number) => {
    if (!student) return
    await api.updateStudent(student.id, { target_role_id: roleId })
    setSelectedRole(roleId)
    await refreshStudent()
  }

  const onUpload = async (file: File | undefined) => {
    if (!file || !student) return
    setUploading(true)
    setCvMsg('')
    try {
      const res = await api.uploadCv(student.id, file)
      setCvMsg(`Extracted ${res.extracted.length} skills from "${file.name}".${res.genai_provider === 'real' ? '' : ' (deterministic fallback — set a GenAI API key for live extraction)'}`)
      await refreshStudent()
    } catch (e: any) {
      setCvMsg('Upload failed: ' + e.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="grid grid-2">
      <div>
        <div className="card">
          <div className="flex between">
            <h3>My profile &amp; CV</h3>
            <label className="btn btn-sm" style={{ cursor: 'pointer' }}>
              <IconUpload size={14} /> {uploading ? 'Extracting…' : 'Upload CV'}
              <input type="file" accept=".txt,.md,.pdf" style={{ display: 'none' }} onChange={(e) => onUpload(e.target.files?.[0])} />
            </label>
          </div>
          {student?.cv_filename && <p className="small muted mb">CV on file: {student.cv_filename}</p>}
          {cvMsg && <p className="small" style={{ color: cvMsg.startsWith('Extracted') ? 'var(--green)' : 'var(--red)' }}>{cvMsg}</p>}
          <div className="divider" />
          <p className="small muted mb">Self-reported profile (extracted from CV by GenAI, unverified)</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(student?.self_reported_skills || []).map((s) => (
              <SkillTag key={s.skill_id} name={s.name} level={s.level} verified={false} />
            ))}
            {(student?.self_reported_skills || []).length === 0 && <span className="muted small">Upload a CV or transcript to build this.</span>}
          </div>
          <div style={{ marginTop: 14 }}>
            <p className="small muted mb">Verified skills (earned via assessments)</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {(student?.verified_skills || []).map((s) => (
                <SkillTag key={s.skill_id} name={s.name} level={s.level} verified={true} />
              ))}
              {(student?.verified_skills || []).length === 0 && <span className="muted small">No verified skills yet.</span>}
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Available roles</h3>
        <p className="card-sub">Select one as your Target Career to see your gap map and match score.</p>
        <div className="searchbar mb">
          <IconSearch size={16} />
          <input placeholder="Search roles or companies…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="stack">
          {filtered.map((r) => (
            <div className="role-card" key={r.id} style={{ border: selectedRole === r.id ? '1.5px solid var(--teal)' : '' }}>
              <div className="rc-head">
                <div>
                  <div className="rc-title">{r.title}</div>
                  <div className="rc-company">{r.company_name}{r.id === selectedRole ? ' · Target Career' : ''}</div>
                </div>
                <button
                  className={`btn btn-sm ${selectedRole === r.id ? '' : 'btn-primary'}`}
                  onClick={() => chooseTarget(r.id)}
                  disabled={!student}
                >
                  {selectedRole === r.id ? '✓ Selected' : 'Select as target'}
                </button>
              </div>
              <div className="rc-desc">{r.description}</div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {r.required_skills.map((s) => (
                  <span className="skill-tag" key={s.skill_id}>{s.name} <span className="lv">{s.required_level}</span></span>
                ))}
              </div>
            </div>
          ))}
          {filtered.length === 0 && <div className="empty">No roles match your search.</div>}
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ Company roles
function CompanyRoles({ company }: { company?: any }) {
  const { roles, setRoles, skills } = useRolesStudents()
  const [editing, setEditing] = useState<any>(null)
  const [showForm, setShowForm] = useState(false)

  const refresh = () => api.roles().then(setRoles)
  useEffect(() => { refresh() }, [])

  const openNew = () => {
    setEditing({
      id: null, title: '', description: '', skillRows: [{ name: '', level: 'Intermediate', category: 'General' }]
    })
    setShowForm(true)
  }
  const openEdit = (r: RoleRecord) => {
    setEditing({
      id: r.id, title: r.title, description: r.description || '',
      skillRows: r.required_skills.map((s) => ({ name: s.name, level: s.required_level, category: s.category || 'General' })),
    })
    setShowForm(true)
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!company) return
    const body = {
      company_id: company.id,
      title: editing.title,
      description: editing.description,
      required_skills: editing.skillRows
        .filter((s: any) => s.name.trim())
        .map((s: any) => ({ name: s.name.trim(), level: s.level, category: s.category || 'General' })),
    }
    if (!body.required_skills.length) return
    try {
      await api.createRole(body)
      setShowForm(false)
      refresh()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const removeRole = async (id: number) => {
    if (!confirm('Delete this role? Students currently targeting it will lose their target.')) return
    await api.deleteRole(id)
    refresh()
  }

  const changeRow = (i: number, patch: any) => {
    setEditing((prev: any) => ({
      ...prev, skillRows: prev.skillRows.map((r: any, idx: number) => (idx === i ? { ...r, ...patch } : r)),
    }))
  }

  return (
    <div>
      <div className="flex between mb">
        <h3 style={{ fontSize: 17 }}>My company roles</h3>
        <button className="btn btn-primary" onClick={openNew}><IconPlus size={15} /> Define role</button>
      </div>

      {showForm && editing && (
        <div className="card mb">
          <h3>{editing.id ? 'Edit role' : 'Define a new role'}</h3>
          <form onSubmit={save}>
            <div className="field"><label>Job title</label>
              <input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} required /></div>
            <div className="field"><label>Description</label>
              <input value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} /></div>
            <p className="small muted mb">Required skills &amp; proficiency levels</p>
            {editing.skillRows.map((row: any, i: number) => (
              <div className="flex" key={i} style={{ marginBottom: 8 }}>
                <input placeholder="Skill name" value={row.name} onChange={(e) => changeRow(i, { name: e.target.value })}
                  list="skill-options" style={{ flex: 1, padding: '8px 12px', border: '1px solid var(--slate-300)', borderRadius: 6 }} />
                <select value={row.level} onChange={(e) => changeRow(i, { level: e.target.value })}
                  style={{ padding: '8px 10px', border: '1px solid var(--slate-300)', borderRadius: 6 }}>
                  {LEVELS.map((l) => <option key={l}>{l}</option>)}
                </select>
                <input placeholder="Category" value={row.category} onChange={(e) => changeRow(i, { category: e.target.value })}
                  style={{ width: 140, padding: '8px 12px', border: '1px solid var(--slate-300)', borderRadius: 6 }} />
                {editing.skillRows.length > 1 && (
                  <button type="button" className="btn btn-sm btn-danger" onClick={() =>
                    setEditing((p: any) => ({ ...p, skillRows: p.skillRows.filter((_: any, idx: number) => idx !== i) }))}>
                    <IconTrash size={13} /></button>
                )}
              </div>
            ))}
            <datalist id="skill-options">{skills.map((s) => <option key={s.id} value={s.name} />)}</datalist>
            <button type="button" className="btn btn-sm" onClick={() =>
              setEditing((p: any) => ({ ...p, skillRows: [...p.skillRows, { name: '', level: 'Intermediate', category: 'General' }] }))}>
              <IconPlus size={13} /> Add skill</button>
            <div className="flex mt" style={{ justifyContent: 'flex-end' }}>
              <button type="button" className="btn" onClick={() => setShowForm(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary"><IconCheck /> Save role</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        {roles.length === 0 && <div className="empty">No roles defined yet.</div>}
        {roles.map((r) => (
          <div className="role-card" key={r.id}>
            <div className="rc-head">
              <div>
                <div className="rc-title">{r.title}</div>
                <div className="rc-company">{r.company_name}</div>
              </div>
              <div className="rc-actions">
                <button className="btn btn-sm" onClick={() => openEdit(r)}><IconEdit size={14} /> Edit</button>
                <button className="btn btn-sm btn-danger" onClick={() => removeRole(r.id)}><IconTrash size={14} /></button>
              </div>
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

// ------------------------------------------------------------------ Read-only
function ReadOnlyBrowse() {
  const { roles } = useRolesStudents()
  return (
    <div className="card">
      <h3>Available roles across companies</h3>
      <div className="stack">
        {roles.map((r) => (
          <div className="role-card" key={r.id}>
            <div className="rc-title">{r.title}</div>
            <div className="rc-company">{r.company_name}</div>
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

