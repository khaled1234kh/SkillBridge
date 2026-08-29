export type Role = 'Student' | 'Company' | 'University Admin'

export interface Session {
  id: number
  email: string
  role: Role
  display_name: string
  entity_type: 'student' | 'company' | 'university'
  entity_id: number | null
}

export interface Skill {
  id: number
  name: string
  category: string
}

export interface RequiredSkill {
  skill_id: number
  name: string
  category: string
  required_level: string
}

export interface RoleRecord {
  id: number
  company_id: number
  title: string
  description?: string
  company_name?: string
  required_skills: RequiredSkill[]
}

export interface SelfReportedSkill {
  skill_id: number
  name: string
  category: string
  level: string
  source: string
}

export interface VerifiedSkill {
  skill_id: number
  name: string
  category: string
  level: string
  verified_at: string
}

export interface Student {
  id: number
  name: string
  email: string
  university: string
  target_role_id: number | null
  target_role?: RoleRecord
  cv_filename?: string | null
  self_reported_skills: SelfReportedSkill[]
  verified_skills: VerifiedSkill[]
}

export interface SkillGap {
  skill_id: number
  skill_name: string
  category: string
  required_level: string
  student_level: string | null
  status: 'strong' | 'gap' | 'missing'
  verified: boolean
}

export interface Analysis {
  student_id: number
  role_id: number
  role_title: string
  company?: string
  match_score: number
  skill_gaps: SkillGap[]
  gap_count: number
}

export interface LearningItem {
  id: number
  skill_id: number
  skill_name: string
  category: string
  explanation: string
  practice_exercise: string
  mini_project: string
  generated_at: string
}

export interface TutorMessage {
  id: number
  skill_id: number | null
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface QuizQuestion {
  question: string
  type: 'multiple_choice' | 'free_text'
  options: string[]
  answer: string
}

export interface IntegrityFlag {
  code: string
  label: string
  severity: string
  detail: string
}

export interface AssessmentAttempt {
  id: number
  student_id: number
  skill_id: number
  skill_name: string
  questions: string
  answers: string
  score: number
  passed: number
  flags: string
  level_before: string
  level_after: string
  created_at: string
}

export interface UniversityStat {
  skill_name: string
  category: string
  count: number
  strong: number
  gap: number
  missing: number
  need_improvement_pct: number
}

export interface UniversityStatsResponse {
  rule: { min_cohort_size: number; satisfied: boolean; student_count: number }
  student_count?: number
  with_target_role?: number
  average_match_score?: number
  skill_stats?: UniversityStat[]
  verified_skills_total?: number
  assessments_total?: number
  message?: string
}

export interface Company {
  id: number
  name: string
  industry: string
}
