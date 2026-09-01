export type Role = 'Student' | 'Company' | 'University Admin'

export interface Session {
  token: string
  id: number
  email: string
  role: Role
  display_name: string
  auth_provider: string
  entity_type: 'student' | 'company' | 'university'
  verified?: boolean
  country?: string
  university?: string
  location?: string
  student?: Student
  company?: Company
  roles?: RoleRecord[]
  analysis?: Analysis | null
  learning?: LearningItem[]
}

export interface UniversityOption {
  country: string
  universities: string[]
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
  company_location?: string
  required_skills: RequiredSkill[]
  is_reference?: number
}

export interface RolesResponse {
  roles: RoleRecord[]
  catalog: RoleRecord[]
  is_company: boolean
  company_id: number | null
  location?: string
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
  cohort_confirmed?: number
  share_public?: number
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

export interface BadgeInfo {
  code: string
  name: string
  desc: string
  hint?: string
  earned: boolean
  earned_at?: string | null
}

export interface ActivitySummary {
  student_id: number
  streak_days: number
  active_days: number
  xp: number
  level: number
  xp_into_level: number
  xp_per_level: number
  assessments_taken: number
  verified_skills: number
  badges: BadgeInfo[]
  leaderboard: { status: string; message?: string }
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

export interface LearningResource {
  rank?: number
  type: string
  title: string
  url: string
  source?: string
  helpfulness?: string
}

export interface RoadmapStep {
  step: number
  title: string
  objective: string
  resource_ranks: number[]
  practice: string
  checkpoint: string
}

export interface Roadmap {
  summary: string
  steps: RoadmapStep[]
}

export interface LearningItem {
  id: number
  skill_id: number
  skill_name: string
  category: string
  explanation: string
  practice_exercise: string
  mini_project: string
  resources: LearningResource[] | null
  roadmap: Roadmap | null
  progress?: number[]
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
  explanation: string
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

export interface GeneratedAssessment {
  skill: Skill
  questions: QuizQuestion[]
  practice: boolean
  previous_results: PerQuestionResult[] | null
  previous_score: number | null
  previous_passed: boolean | null
}

export interface PerQuestionResult {
  index: number
  type: string
  correct: boolean
  answer: string
}

export interface AssessmentResult {
  score: number
  passed: boolean
  flags: IntegrityFlag[]
  per_question: PerQuestionResult[]
  level_before: string
  level_after: string
  analysis: Analysis | null
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
  rule: { min_cohort_size: number; satisfied: boolean; student_count: number; confirmed_count?: number }
  student_count?: number
  with_target_role?: number
  average_match_score?: number
  skill_stats?: UniversityStat[]
  verified_skills_total?: number
  assessments_total?: number
  message?: string
}

export interface CohortResponse {
  student_count: number
  confirmed_count: number
  min_cohort_size: number
  students: { index: number; confirmed: boolean }[]
}

export interface Company {
  id: number
  name: string
  industry: string
}

export interface Candidate {
  student_id: number
  name: string
  email: string
  university: string
  match_score: number
  gap_count: number
  verified_count: number
}

export interface SkillCoverageRow {
  skill_id: number
  skill_name: string
  category?: string
  required_level: string
  strong: number
  gap: number
  missing: number
  coverage_pct: number
  n_candidates: number
}

export interface RoleSkillCoverage {
  role_id: number
  role_title: string
  candidate_count: number
  skills: SkillCoverageRow[]
}

export interface GoogleConfig {
  configured: boolean
  demo: boolean
}

export interface PublicVerifiedSkill {
  skill_id: number
  name: string
  category: string
  level: string
  verified_at: string
}

export interface PublicProfile {
  student_id: number
  name: string
  university: string
  target_role: { title: string; company?: string } | null
  verified_skills: PublicVerifiedSkill[]
}

export interface RecentJob {
  title: string
  company: string
  url: string
  date?: string
  tags?: string[]
  location?: string
  country?: string
  source?: string
  seniority?: string
  match_pct?: number
  match_reason?: string
}

export interface CareerRoadmapSkill {
  name: string
  category: string
}

export interface CareerRoadmapPhase {
  phase: number
  title: string
  goal: string
  skills: CareerRoadmapSkill[]
  deliverables: string[]
  checkpoint: string
}

export interface CareerRoadmap {
  role_title: string | null
  summary: string
  student_starting_point?: number
  phase_count: number
  phases: CareerRoadmapPhase[]
}