import type {
  ActivitySummary, Analysis, AssessmentAttempt, Candidate, CareerRoadmap, CohortResponse, Company, GeneratedAssessment,
  GoogleConfig, LearningItem, QuizQuestion, PublicProfile, RoleRecord, RolesResponse, RoleSkillCoverage, Skill, Student,
  Session, TutorMessage, UniversityStatsResponse, UniversityOption, RecentJob,
} from './types'

const BASE = ''
const TOKEN_KEY = 'skillbridge_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(BASE + path, { ...options, headers })
  if (!res.ok) {
    let detail = `Request failed: ${res.status}`
    try {
      const data = await res.json()
      if (data && data.detail) detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch { /* non-JSON error body */ }
    if (res.status === 401) setToken(null)
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  // ---- auth
  login: (email: string, password: string) => {
    const p = req<Session & { entity_type: string }>('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
    return p.then((s) => { setToken(s.token); return s })
  },
  signup: (email: string, password: string, display_name: string, role: string, university?: string, country?: string, industry?: string, location?: string) => {
    const p = req<any>('/api/auth/signup', { method: 'POST', body: JSON.stringify({ email, password, display_name, role, university, country, industry, location }) })
    return p.then((s) => { setToken(s.token); return s })
  },
  logout: () => {
    try { return req<any>('/api/auth/logout', { method: 'POST' }).finally(() => setToken(null)) }
    catch { setToken(null); return Promise.resolve({ ok: true }) }
  },
  me: () => req<Session>('/api/auth/me'),
  googleConfig: () => req<GoogleConfig>('/api/auth/google/config'),
  googleDemo: (email: string, display_name: string) =>
    req<any>('/api/auth/google/demo', { method: 'POST', body: JSON.stringify({ email, display_name }) }),
  googleComplete: (google_sub: string, role: string, opts?: { university?: string; country?: string; industry?: string; location?: string }) => {
    const p = req<any>('/api/auth/google/complete', { method: 'POST', body: JSON.stringify({ google_sub, role, university: opts?.university, country: opts?.country, industry: opts?.industry, location: opts?.location }) })
    return p.then((s) => { setToken(s.token); return s })
  },
  resetRequest: (email: string) =>
    req<{ ok: boolean; reset_token?: string; message?: string }>('/api/auth/reset/request', { method: 'POST', body: JSON.stringify({ email }) }),
  resetConfirm: (token: string, new_password: string) =>
    req<{ ok: boolean }>('/api/auth/reset/confirm', { method: 'POST', body: JSON.stringify({ token, new_password }) }),
  verifyEmail: (token: string) =>
    req<{ ok: boolean }>('/api/auth/verify', { method: 'POST', body: JSON.stringify({ token }) }),
  universities: () => req<UniversityOption[]>('/api/universities'),

  // ---- catalog
  skills: () => req<Skill[]>('/api/skills'),
  roles: () => req<RolesResponse>('/api/roles'),
  catalogRoles: () => req<RoleRecord[]>('/api/roles/catalog'),
  createRole: (body: any) => req<RoleRecord>('/api/roles', { method: 'POST', body: JSON.stringify(body) }),
  updateRole: (id: number, body: any) => req<RoleRecord>(`/api/roles/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteRole: (id: number) => req<{ deleted: boolean }>(`/api/roles/${id}`, { method: 'DELETE' }),
  companies: () => req<Company[]>('/api/companies'),
  candidates: (roleId: number) => req<Candidate[]>(`/api/company/roles/${roleId}/candidates`),
  roleSkillCoverage: (roleId: number) => req<RoleSkillCoverage>(`/api/company/roles/${roleId}/skills`),

  // ---- students
  student: (id: number) => req<Student>(`/api/students/${id}`),
  updateStudent: (id: number, body: any) => req<Student>(`/api/students/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  uploadCv: async (studentId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(`${BASE}/api/students/${studentId}/cv`, { method: 'POST', body: fd, headers })
    if (!res.ok) {
      let detail = 'CV upload failed'
      try { const d = await res.json(); detail = d.detail || detail } catch { /* ignore */ }
      if (res.status === 401) setToken(null)
      throw new Error(detail)
    }
    return res.json()
  },

  analysis: (studentId: number) => req<Analysis>(`/api/students/${studentId}/analysis`),

  learning: (studentId: number) => req<LearningItem[]>(`/api/students/${studentId}/learning`),
  generateLearning: (studentId: number, skillId: number) =>
    req<LearningItem>(`/api/students/${studentId}/learning/generate`, { method: 'POST', body: JSON.stringify({ skill_id: skillId }) }),
  learningProgress: (studentId: number, skillId: number, steps: number[]) =>
    req<LearningItem>(`/api/students/${studentId}/learning/${skillId}/progress`, { method: 'POST', body: JSON.stringify({ steps }) }),

  publicProfile: (studentId: number) => req<PublicProfile>(`/api/public/verified/${studentId}`),

  tutorHistory: (studentId: number) => req<TutorMessage[]>(`/api/students/${studentId}/tutor`),
  tutorSend: (studentId: number, message: string, skillId?: number | null) =>
    req<TutorMessage>(`/api/students/${studentId}/tutor`, { method: 'POST', body: JSON.stringify({ message, skill_id: skillId }) }),

  generateAssessment: (studentId: number, skillId: number, opts: { practice?: boolean; num_questions?: number } = {}) =>
    req<GeneratedAssessment>(`/api/students/${studentId}/assessments/generate`, { method: 'POST', body: JSON.stringify({ skill_id: skillId, practice: !!opts.practice, num_questions: opts.num_questions || 10 }) }),
  submitAssessment: (studentId: number, body: any) =>
    req<any>(`/api/students/${studentId}/assessments`, { method: 'POST', body: JSON.stringify(body) }),
  studentAssessments: (studentId: number) => req<AssessmentAttempt[]>(`/api/students/${studentId}/assessments`),
  studentActivity: (studentId: number) => req<ActivitySummary>(`/api/students/${studentId}/activity`),

  // ---- university
  universityStats: () => req<UniversityStatsResponse>('/api/university/stats'),
  universityCohort: () => req<CohortResponse>('/api/university/cohort'),
  universityConfirm: () => req<CohortResponse>('/api/university/cohort/confirm', { method: 'POST', body: JSON.stringify({ confirm: true }) }),

  // ---- recent jobs
  recentJobs: () => req<{ source: 'live' | 'fallback'; jobs: RecentJob[] }>('/api/jobs/recent'),

  // ---- full career roadmap
  careerRoadmap: (studentId: number) => req<CareerRoadmap>(`/api/students/${studentId}/career-roadmap`),
}