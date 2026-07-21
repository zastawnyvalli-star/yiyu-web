"""FastAPI main application for the adaptive screening agent.

Provides three endpoints:
- POST /start  : Initialize a screening session
- POST /answer : Process a user answer, return adaptive next question
- POST /report : Generate final screening report
"""

import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    StartRequest, StartResponse,
    AnswerRequest, AnswerResponse,
    ReportRequest, ReportResponse,
)
from session_manager import (
    create_session, get_session, add_answer,
    update_round, mark_done, SessionState,
)
from config import MIN_ROUNDS, MAX_ROUNDS, DIMENSIONS, INITIAL_DIMENSION_ORDER
from coverage_tracker import classify_dimension, calculate_coverage, calculate_confidence
from adaptive_engine import should_continue, select_next_dimension
from question_engine import generate_initial_question, generate_next_question
from report_generator import generate_report
from llm_client import is_llm_available
from fallback_topics import TOPIC_LABELS

app = FastAPI(
    title="忆语安康 智能筛查智能体",
    description="AI Adaptive MCI Screening Agent",
    version="2.0.0",
)

# CORS: allow frontend from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health():
    """Health check endpoint."""
    return {
        "ok": True,
        "service": "yiyu-agent",
        "version": "2.0.0",
        "llm_available": is_llm_available(),
        "config": {
            "minRounds": MIN_ROUNDS,
            "maxRounds": MAX_ROUNDS,
            "dimensions": DIMENSIONS,
        },
    }


@app.post("/start", response_model=StartResponse)
async def start(req: StartRequest):
    """Initialize a new screening session.

    Accepts user profile for education-based question adaptation.
    Returns the first question and session metadata.
    """
    try:
        # Create session with profile
        profile = req.profile.model_dump() if req.profile else {}
        session_id = create_session(profile)
        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        # Generate first question (education-appropriate opening)
        first_question = generate_initial_question(session)

        # Record the opening as an AI message
        session.round = 1

        return StartResponse(
            sessionId=session_id,
            message=first_question,
            round=1,
            totalMinRounds=MIN_ROUNDS,
            totalMaxRounds=MAX_ROUNDS,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/answer", response_model=AnswerResponse)
async def answer(req: AnswerRequest):
    """Process a user's answer and return the adaptive next step.

    This is the core adaptive endpoint:
    1. Classifies the answer into a dimension
    2. Records it in the session
    3. Runs the adaptive continuation algorithm
    4. Returns next question + continuation metadata

    Frontend uses shouldContinue + round to decide when to call /report.
    """
    try:
        # Handle missing session (create one if needed)
        session_id = req.sessionId
        if not session_id:
            session_id = create_session({})
        session = get_session(session_id)
        if not session:
            session_id = create_session({})
            session = get_session(session_id)
            if not session:
                raise HTTPException(status_code=500, detail="Failed to get or create session")

        text = req.text.strip()
        if not text:
            # Empty answer - return a gentle prompt
            return AnswerResponse(
                nextQuestion="我没有听清楚，您能再说一遍吗？",
                round=session.round,
                shouldContinue=True,
                reason="需要重新确认回答内容",
                coverage=session.coverage,
                confidence=session.confidence,
                sessionId=session_id,
            )

        # Determine current dimension context
        current_dim = ""
        if session.answers:
            current_dim = session.answers[-1].get("dimension", "")

        # 1. Classify answer into a dimension
        dimension = classify_dimension(text, current_dim)

        # 2. Record the answer
        # Get last AI question for context
        last_question = ""
        for a in session.answers:
            if a.get("question"):
                last_question = a["question"]

        topic_label = TOPIC_LABELS.get(dimension, dimension)
        add_answer(session, text, dimension, topic=topic_label, question=last_question)

        # Update round counter (answers count = round number)
        update_round(session)

        # 3. Update dimension scores (simple heuristic)
        _update_dimension_scores(session)

        # 4. Run adaptive algorithm
        continue_flag, reason, coverage, confidence = should_continue(session)

        # Store score snapshot for stability tracking
        session.score_history.append(dict(session.dimension_scores))

        # 5. Generate next question
        if continue_flag:
            next_dim = select_next_dimension(session)
            llm_ok = is_llm_available()
            next_question = generate_next_question(session, next_dim, llm_available=llm_ok)
        else:
            # Natural end or forced end
            mark_done(session, forced=session.forced_end)
            if session.forced_end:
                next_question = (
                    "好的，咱们聊了不少了。感谢您跟我分享了这么多日常情况。"
                    "我来把这些内容整理成一份报告，有些地方我们下次还可以再聊。"
                )
            else:
                next_question = (
                    "好的，我们聊得很充分了。感谢您跟我分享这些日常情况。"
                    "您先歇一小会儿，我来把这些内容整理成一份简单的报告。"
                )

        return AnswerResponse(
            nextQuestion=next_question,
            round=session.round,
            shouldContinue=continue_flag,
            reason=reason,
            coverage=coverage,
            confidence=confidence,
            sessionId=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report", response_model=ReportResponse)
async def report(req: ReportRequest):
    """Generate the final screening report.

    Called by frontend after shouldContinue becomes false or round >= 20.
    """
    try:
        session_id = req.sessionId
        if not session_id:
            raise HTTPException(status_code=400, detail="sessionId is required")

        session = get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Mark done if not already
        if not session.done:
            mark_done(session)

        report_data = generate_report(session)

        return ReportResponse(
            report=report_data,
            sessionId=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _update_dimension_scores(session: SessionState) -> None:
    """Update per-dimension scores based on the latest answer.

    A simple heuristic: each dimension score is the proportion of
    "good" answers (long enough, not contradictory) in that dimension.
    This feeds into coverage and stability calculations.
    """
    for dim in DIMENSIONS:
        answers = session.dimension_answers.get(dim, [])
        if not answers:
            session.dimension_scores[dim] = 0.0
            continue

        # Score based on answer quality
        good_count = 0
        for a in answers:
            text_len = a.get("length", len(a.get("text", "")))
            # Good answer: reasonable length, not just "嗯" or "好"
            if text_len >= 20:
                good_count += 1
            elif text_len >= 10:
                good_count += 0.5

        raw_score = good_count / max(1, len(answers))
        # Scale to 0-1 range
        session.dimension_scores[dim] = round(min(1.0, raw_score), 2)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8899)
