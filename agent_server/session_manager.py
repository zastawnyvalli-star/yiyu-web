"""In-memory session state management."""

import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import DIMENSIONS, EDUCATION_LEVEL_MAP


@dataclass
class SessionState:
    """Complete state for one screening session."""
    session_id: str
    profile: dict = field(default_factory=dict)
    round: int = 0
    answers: List[dict] = field(default_factory=list)
    done: bool = False
    coverage: float = 0.0
    confidence: float = 0.0
    # Per-dimension tracking
    dimension_scores: Dict[str, float] = field(default_factory=lambda: {
        d: 0.0 for d in DIMENSIONS
    })
    dimension_answers: Dict[str, List[dict]] = field(default_factory=lambda: {
        d: [] for d in DIMENSIONS
    })
    # Round-by-round tracking for stability
    score_history: List[Dict[str, float]] = field(default_factory=list)
    # Contradictions detected
    contradictions: List[str] = field(default_factory=list)
    # Education level (mapped)
    education_level: str = "secondary_low"
    # Forced end marker
    forced_end: bool = False
    # All AI questions asked so far (for deduplication)
    asked_questions: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


# In-memory session store
_sessions: Dict[str, SessionState] = {}


def create_session(profile: Optional[dict] = None) -> str:
    """Create a new screening session. Returns session_id."""
    session_id = str(uuid.uuid4())[:12]
    edu_raw = (profile or {}).get("education", "初中")
    edu_level = EDUCATION_LEVEL_MAP.get(edu_raw, "secondary_low")
    _sessions[session_id] = SessionState(
        session_id=session_id,
        profile=profile or {},
        education_level=edu_level,
    )
    return session_id


def get_session(session_id: str) -> Optional[SessionState]:
    """Retrieve a session by ID. Returns None if not found."""
    return _sessions.get(session_id)


def add_answer(session: SessionState, text: str, dimension: str, topic: str = "",
               question: str = "") -> None:
    """Record an answer in the session."""
    entry = {
        "round": session.round + 1,
        "text": text,
        "dimension": dimension,
        "topic": topic or dimension,
        "question": question,
        "length": len(text),
    }
    session.answers.append(entry)
    if dimension in session.dimension_answers:
        session.dimension_answers[dimension].append(entry)


def update_round(session: SessionState) -> None:
    """Increment the round counter."""
    session.round += 1


def mark_done(session: SessionState, forced: bool = False) -> None:
    """Mark the session as complete."""
    session.done = True
    session.forced_end = forced


def cleanup_old_sessions(max_age_seconds: int = 3600) -> int:
    """Remove sessions older than max_age_seconds. Returns count removed."""
    now = time.time()
    to_remove = [
        sid for sid, s in _sessions.items()
        if now - s.created_at > max_age_seconds
    ]
    for sid in to_remove:
        del _sessions[sid]
    return len(to_remove)
