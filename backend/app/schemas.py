from typing import Optional, List, Literal
from pydantic import BaseModel, EmailStr, Field

# ---- Auth ----
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1)
    role: Literal["Student", "Company", "University Admin"]
    country: Optional[str] = None
    university: Optional[str] = None
    industry: Optional[str] = None
    model_config = {"extra": "forbid"}

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    model_config = {"extra": "forbid"}

class ResetRequest(BaseModel):
    email: EmailStr
    model_config = {"extra": "forbid"}

class ResetConfirmRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
    model_config = {"extra": "forbid"}

class VerifyRequest(BaseModel):
    token: str
    model_config = {"extra": "forbid"}

# ---- Skills ----
class CreateSkillRequest(BaseModel):
    name: str = Field(min_length=1)
    category: str = "General"
    model_config = {"extra": "forbid"}

# ---- Roles ----
class RoleSkill(BaseModel):
    name: str = Field(min_length=1)
    level: Literal["Beginner", "Intermediate", "Advanced"]
    category: str = "General"
    model_config = {"extra": "forbid"}

class CreateRoleRequest(BaseModel):
    title: str = Field(min_length=1)
    description: Optional[str] = None
    required_skills: List[RoleSkill] = Field(default_factory=list)
    model_config = {"extra": "forbid"}

class UpdateRoleRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[List[RoleSkill]] = None
    model_config = {"extra": "forbid"}

# ---- Students ----
class UpdateStudentRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    university: Optional[str] = None
    target_role_id: Optional[int] = None
    cv_filename: Optional[str] = None
    model_config = {"extra": "forbid"}

# ---- Learning ----
class GenerateLearningRequest(BaseModel):
    skill_id: int
    model_config = {"extra": "forbid"}

# ---- Assessments ----
class GenerateAssessmentRequest(BaseModel):
    skill_id: int
    num_questions: int = Field(default=10, ge=3, le=20)
    practice: bool = False
    model_config = {"extra": "forbid"}

class SubmitAssessmentRequest(BaseModel):
    skill_id: int
    questions: List[dict]
    answers: List[str]
    total_seconds: int
    tab_switches: int = 0
    free_text_answers: List[str] = Field(default_factory=list)
    model_config = {"extra": "forbid"}

# ---- Tutor ----
class TutorChatRequest(BaseModel):
    message: str = Field(min_length=1)
    skill_id: Optional[int] = None
    model_config = {"extra": "forbid"}