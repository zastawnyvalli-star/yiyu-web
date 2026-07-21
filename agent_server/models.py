"""Pydantic models for request/response schemas."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class Profile(BaseModel):
    """User profile submitted at screening start."""
    name: str = ""
    gender: str = ""
    birthDate: str = ""
    education: str = "初中"  # 小学及以下|初中|高中/中专|大专|本科及以上
    dialect: Optional[str] = "普通话"
    familyAccount: Optional[str] = ""


class StartRequest(BaseModel):
    """POST /start request body."""
    profile: Optional[Profile] = None


class StartResponse(BaseModel):
    """POST /start response."""
    sessionId: str
    message: str
    round: int = 1
    totalMinRounds: int = 10
    totalMaxRounds: int = 20


class AnswerRequest(BaseModel):
    """POST /answer request body."""
    sessionId: Optional[str] = None
    text: str


class AnswerResponse(BaseModel):
    """POST /answer response with adaptive continuation info."""
    nextQuestion: str
    round: int
    shouldContinue: bool
    reason: Optional[str] = None
    coverage: float = 0.0
    confidence: float = 0.0
    sessionId: Optional[str] = None


class ReportRequest(BaseModel):
    """POST /report request body."""
    sessionId: Optional[str] = None


class ReportResponse(BaseModel):
    """POST /report response."""
    report: Dict[str, Any]
    sessionId: Optional[str] = None
