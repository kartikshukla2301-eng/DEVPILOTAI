"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Language = Literal["python", "javascript", "typescript", "java", "cpp", "c", "go"]
Severity = Literal["critical", "high", "medium", "low", "info"]
Category = Literal["bug", "quality", "security", "performance"]
Level = Literal["beginner", "intermediate", "advanced"]
Theme = Literal["dark", "light", "system"]

SUPPORTED_LANGUAGES: list[str] = ["python", "javascript", "typescript", "java", "cpp", "c", "go"]
SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# ---------- auth / users ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be blank")
        return v

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    bio: str = ""
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class ProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=500)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


# ---------- settings ----------
class SettingsOut(BaseModel):
    theme: Theme = "dark"
    default_language: Language = "python"
    explanation_level: Level = "intermediate"
    use_ai: bool = True
    updated_at: datetime | None = None


class SettingsUpdateIn(BaseModel):
    theme: Theme | None = None
    default_language: Language | None = None
    explanation_level: Level | None = None
    use_ai: bool | None = None


class AIStatusOut(BaseModel):
    ai_configured: bool
    mode: Literal["ai", "local"]
    model: str | None
    provider_host: str | None


# ---------- projects ----------
class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)
    language: Language | None = None


class ProjectUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    language: Language | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    language: str | None
    review_count: int = 0
    created_at: datetime
    updated_at: datetime


# ---------- code review ----------
class Finding(BaseModel):
    id: str
    category: Category
    severity: Severity
    title: str
    description: str
    recommendation: str
    line: int | None = None
    end_line: int | None = None
    column: int | None = None
    snippet: str | None = None
    rule: str | None = None
    source: Literal["static", "ai"] = "static"
    tool: str = "devpilot"


class CodeInput(BaseModel):
    code: str = Field(min_length=1)
    language: Language
    filename: str | None = Field(default=None, max_length=255)

    @field_validator("code")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Code cannot be empty")
        return v


class ReviewIn(CodeInput):
    categories: list[Category] = Field(default_factory=lambda: ["bug", "quality", "security", "performance"])
    project_id: str | None = None
    title: str | None = Field(default=None, max_length=200)
    use_ai: bool = True
    save: bool = True

    @field_validator("categories")
    @classmethod
    def non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("Select at least one analysis category")
        return list(dict.fromkeys(v))


class ReviewMetrics(BaseModel):
    lines_total: int
    lines_code: int
    lines_comment: int
    functions: int
    classes: int
    max_complexity: int | None = None
    avg_complexity: float | None = None
    max_nesting: int


class ReviewOut(BaseModel):
    id: str | None
    title: str
    filename: str
    language: str
    categories: list[str]
    score: int
    grade: str
    summary: dict[str, int]
    category_summary: dict[str, int]
    findings: list[Finding]
    metrics: ReviewMetrics
    tools_used: list[str]
    ai_used: bool
    ai_summary: str | None = None
    ai_error: str | None = None
    suggested_code: str | None = None
    suggested_code_source: Literal["static", "ai"] | None = None
    code: str
    project_id: str | None = None
    saved: bool
    created_at: datetime
    disclaimer: str


class ReviewListItem(BaseModel):
    id: str
    title: str
    filename: str
    language: str
    score: int
    grade: str
    summary: dict[str, int]
    total_findings: int
    max_severity: str | None
    ai_used: bool
    project_id: str | None
    created_at: datetime


class Paginated(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


# ---------- debug ----------
class DebugIn(CodeInput):
    error_message: str = Field(min_length=1, max_length=20000)
    context: str = Field(default="", max_length=5000)
    use_ai: bool = True


class DebugOut(BaseModel):
    id: str | None
    language: str
    error_type: str
    explanation: str
    root_cause: str
    location: dict[str, Any] | None
    steps: list[str]
    suggested_code: str | None
    prevention_tips: list[str]
    confidence: Literal["high", "medium", "low"]
    ai_used: bool
    ai_error: str | None = None
    created_at: datetime


# ---------- explain ----------
class ExplainIn(CodeInput):
    level: Level = "intermediate"
    use_ai: bool = True


class LineExplanation(BaseModel):
    line: int
    code: str
    explanation: str


class SymbolExplanation(BaseModel):
    name: str
    kind: str
    line: int | None = None
    explanation: str


class ExplainOut(BaseModel):
    id: str | None
    language: str
    level: str
    purpose: str
    lines: list[LineExplanation]
    functions: list[SymbolExplanation]
    variables: list[SymbolExplanation]
    algorithm: str
    time_complexity: str
    space_complexity: str
    complexity_note: str
    ai_used: bool
    ai_error: str | None = None
    created_at: datetime


# ---------- optimize ----------
class OptimizeIn(CodeInput):
    use_ai: bool = True


class Suggestion(BaseModel):
    kind: Literal["performance", "readability", "pattern"]
    title: str
    description: str
    line: int | None = None
    before: str | None = None
    after: str | None = None
    impact: Literal["high", "medium", "low"] = "medium"


class OptimizeOut(BaseModel):
    id: str | None
    language: str
    original_code: str
    optimized_code: str
    changed: bool
    suggestions: list[Suggestion]
    summary: str
    ai_used: bool
    ai_error: str | None = None
    created_at: datetime


# ---------- documentation ----------
class DocsIn(CodeInput):
    project_name: str | None = Field(default=None, max_length=100)
    use_ai: bool = True


class DocsOut(BaseModel):
    id: str | None
    language: str
    markdown: str
    symbols: dict[str, int]
    ai_used: bool
    ai_error: str | None = None
    created_at: datetime
