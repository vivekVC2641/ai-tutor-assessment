from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=3)


class IngestRequest(BaseModel):
    file_path: str = Field(min_length=1)


class IngestResponse(BaseModel):
    file_path: str
    sections: int
    chunks: int
    index_created: bool


class AskResponse(BaseModel):
    question: str
    tutor_answer: str
    sources: list[str]
    used_chunks: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    follow_up_hint: str | None = None
    unsupported_claims: list[str] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    question: str = Field(min_length=3)
    student_answer: str = Field(min_length=1)
    session_id: str | None = None
    # Optional: when provided, `/answer` will evaluate student vs this ideal answer directly.
    # This is useful for a "teacher-generated answer" evaluation flow while keeping the assessment API name `/answer`.
    ideal_answer: str | None = None


class EvaluationResponse(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    confidence: float = Field(ge=0.0, le=1.0)


class ReviewRequest(BaseModel):
    evaluation_id: str = Field(min_length=1)
    action: str = Field(pattern="^(approve|override)$")
    human_score: float | None = Field(default=None, ge=0.0, le=1.0)
    reviewer_id: str = "human-reviewer"
    reason_for_override: str = ""
    feedback: str = ""


class ReviewRecord(BaseModel):
    question: str
    student_answer: str
    ai_score: float
    human_score: float | None
    final_score: float
    reviewer_id: str
    reason_for_override: str
    override_applied: bool
    feedback: str
    timestamp: datetime


class ReviewStatsResponse(BaseModel):
    total_reviews: int
    override_count: int
    override_rate: float = Field(ge=0.0, le=1.0)
    average_score_delta: float


class FullEvaluationResponse(BaseModel):
    evaluation_id: str
    session_id: str
    question_id: str
    question: str
    student_answer: str
    ai_answer: str
    sources: list[str]
    used_chunks: list[dict[str, Any]] = Field(default_factory=list)
    ai_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    feedback: str
    decision_source: str = Field(description="ai or human")
    status: str = Field(description="pending_review or finalized")


class OrchestratorResponse(BaseModel):
    question: str
    tutor_answer: str
    evaluation: EvaluationResponse | None
    sources: list[str]
    used_chunks: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    follow_up_hint: str | None = None
    unsupported_claims: list[str] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)
