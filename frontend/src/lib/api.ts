import type {
  Analysis, AssessmentAttempt, Company, LearningItem, QuizQuestion, RoleRecord,
  Skill, Student, Session, TutorMessage, UniversityStatsResponse, Role,
} from './types'

const BASE = ''

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `Request failed: ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  login: (email: string, password: string) =>
    req<Session>('/api/login', { method: 'POST', body: JSON.stringify({ email, password }) }),

  me: (userId: number) =>
    req<{ id: number; role: Role; display_name: string; entity_type: string;
          student?: Student; company?: Company; roles?: RoleRecord[]; analysis?: Analysis }>(
      `/api/me/${userId}`),

  skills: () => req<Skill[]>('/api/skills'),
  roles: () => req<RoleRecord[]>('/api/roles'),
  createRole: (body: any) => req<RoleRecord>('/api/roles', { method: 'POST', body: JSON.stringify(body) }),
  updateRole: (id: number, body: any) => req<RoleRecord>(`/api/roles/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteRole: (id: number) => req<{ deleted: boolean }>(`/api/roles/${id}`, { method: 'DELETE' }),
  companies: () => req<Company[]>('/api/companies'),

  student: (id: number) => req<Student>(`/api/students/${id}`),
  students: () => req<Student[]>('/api/students'),
  updateStudent: (id: number, body: any) => req<Student>(`/api/students/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  uploadCv: async (studentId: number, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(`${BASE}/api/students/${studentId}/cv`, { method: 'POST', body: fd })
    if (!res.ok) throw new Error('CV upload failed')
    return res.json()
  },

  analysis: (studentId: number) => req<Analysis>(`/api/students/${studentId}/analysis`),

  learning: (studentId: number) => req<LearningItem[]>(`/api/students/${studentId}/learning`),
  generateLearning: (studentId: number, skillId: number) =>
    req<LearningItem>(`/api/students/${studentId}/learning/generate`, { method: 'POST', body: JSON.stringify({ skill_id: skillId }) }),

  tutorHistory: (studentId: number) => req<TutorMessage[]>(`/api/students/${studentId}/tutor`),
  tutorSend: (studentId: number, message: string, skillId?: number | null) =>
    req<TutorMessage>(`/api/students/${studentId}/tutor`, { method: 'POST', body: JSON.stringify({ message, skill_id: skillId }) }),

  generateAssessment: (studentId: number, skillId: number) =>
    req<{ skill: Skill; questions: QuizQuestion[] }>(`/api/students/${studentId}/assessments/generate`, { method: 'POST', body: JSON.stringify({ skill_id: skillId }) }),
  submitAssessment: (studentId: number, body: any) =>
    req<any>(`/api/students/${studentId}/assessments`, { method: 'POST', body: JSON.stringify(body) }),
  studentAssessments: (studentId: number) => req<AssessmentAttempt[]>(`/api/students/${studentId}/assessments`),

  universityStats: () => req<UniversityStatsResponse>('/api/university/stats'),
}
