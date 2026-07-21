"""Question generation engine.

Two modes:
1. LLM mode (primary): uses AI to generate natural, context-aware questions
2. Fallback mode: uses template bank when LLM is unavailable

Education level is used ONLY to adjust question wording, never for scoring.
"""

from typing import Optional
from session_manager import SessionState
from config import (
    DIMENSIONS, INITIAL_DIMENSION_ORDER, MIN_ROUNDS,
    EDUCATION_INSTRUCTIONS, OPENING_MESSAGES,
)
from education_adapter import get_education_level, get_education_instruction
from fallback_topics import (
    FALLBACK_QUESTIONS, FOLLOW_UP_QUESTIONS, CLARIFY_QUESTIONS, TOPIC_LABELS,
)
from coverage_tracker import classify_dimension
from llm_client import get_llm_client


# Track which fallback question index was used per dimension
_dimension_question_index: dict = {}


def generate_initial_question(session: SessionState) -> str:
    """Generate the very first question of the screening.

    Uses education-appropriate opening message.
    """
    edu_level = session.education_level
    # Use opening message if available for this education level
    opening = OPENING_MESSAGES.get(edu_level, OPENING_MESSAGES["secondary_low"])
    return opening


def generate_next_question(
    session: SessionState,
    target_dimension: str,
    llm_available: bool = True,
) -> str:
    """Generate the next question for the given dimension.

    Args:
        session: Current session state with all history
        target_dimension: Which dimension to ask about
        llm_available: Whether LLM API is reachable

    Returns:
        A question string ready to display to the user
    """
    # Determine question type
    question_type = _determine_question_type(session)

    if llm_available:
        try:
            return _generate_llm_question(session, target_dimension, question_type)
        except Exception:
            pass  # Fall through to template mode

    # Fallback: use template bank
    return _generate_fallback_question(session, target_dimension, question_type)


def _determine_question_type(session: SessionState) -> str:
    """Determine what kind of question to ask next.

    Returns: "continue" | "follow_up" | "clarify"
    """
    if not session.answers:
        return "continue"

    last = session.answers[-1]

    # Check for contradictions needing clarification
    if session.contradictions and session.round >= MIN_ROUNDS:
        return "clarify"

    # Check for short answers needing follow-up
    if last.get("length", len(last.get("text", ""))) <= 20:
        return "follow_up"

    # Check if dimension is being revisited for depth
    dim = last.get("dimension", "")
    if dim and len(session.dimension_answers.get(dim, [])) >= 2:
        return "follow_up"

    return "continue"


def _generate_llm_question(
    session: SessionState,
    target_dimension: str,
    question_type: str,
) -> str:
    """Generate question using LLM API."""
    client = get_llm_client()
    if client is None:
        raise Exception("LLM client not configured")

    # Build the prompt
    education_instruction = get_education_instruction(session.education_level)

    # Summarize previous answers for context
    answer_summary = _build_answer_summary(session)
    dim_answers = _build_dimension_answer_summary(session, target_dimension)

    # Determine type-specific instruction
    type_instruction = {
        "continue": "自然地过渡到新话题，问题要像日常聊天一样。",
        "follow_up": (
            "针对这个维度进行深入追问。问题要具体，引导用户给出更多细节。"
            "不要让对方觉得你在质疑或测试他。"
        ),
        "clarify": (
            "温和地请用户澄清之前说法中不太一致的地方。"
            "不要直接说'你前后矛盾'，而是自然地再问一次，给用户重新表达的机会。"
        ),
    }.get(question_type, "")

    system_prompt = (
        "你是一位温和、耐心的认知健康筛查对话助手，正在与一位老年人进行日常聊天。"
        "你的任务是自然地引导对话，了解老年人在七个方面的日常表现："
        "记忆、定向、语言表达、执行能力、情绪、睡眠、日常生活。"
        "\n\n"
        "重要原则：\n"
        "1. 永远不要提及'测试'、'评估'、'筛查'、'诊断'等词\n"
        "2. 问题要像家人朋友聊天一样自然\n"
        "3. 一次只问一个问题或一个主题\n"
        "4. 尊重对方，用'您'称呼\n"
        "5. 不要评判对方的回答\n"
        "6. 每次只输出问题本身，不要加任何说明或前缀"
    )

    user_prompt = (
        f"当前是第 {session.round + 1} 轮对话。\n\n"
        f"目标维度：{target_dimension}\n"
        f"问题类型：{question_type}\n\n"
        f"教育背景适配要求：{education_instruction}\n\n"
        f"用户之前回答的维度总结：\n{answer_summary}\n\n"
        f"在「{target_dimension}」方面，用户之前说过：\n{dim_answers}\n\n"
        f"{type_instruction}\n\n"
        f"请生成一个自然、温和的下一个问题。只输出问题文本，不要有任何其他内容。"
    )

    response = client.chat(
        messages=[{"role": "user", "content": user_prompt}],
        system_prompt=system_prompt,
        max_tokens=200,
        temperature=0.7,
    )
    return response.strip()


def _build_answer_summary(session: SessionState) -> str:
    """Build a brief summary of which dimensions have been covered."""
    lines = []
    for dim in DIMENSIONS:
        answers = session.dimension_answers.get(dim, [])
        if answers:
            count = len(answers)
            last_text = answers[-1]["text"][:80]
            lines.append(f"- {dim}（{count}次）：...{last_text}...")
        else:
            lines.append(f"- {dim}：尚未涉及")
    return "\n".join(lines) if lines else "尚无回答记录"


def _build_dimension_answer_summary(session: SessionState, dimension: str) -> str:
    """Build summary of answers in a specific dimension."""
    answers = session.dimension_answers.get(dimension, [])
    if not answers:
        return "尚未问及此维度"

    lines = []
    for i, a in enumerate(answers):
        lines.append(f"第{a['round']}轮：{a['text'][:120]}")
    return "\n".join(lines)


def _generate_fallback_question(
    session: SessionState,
    target_dimension: str,
    question_type: str,
) -> str:
    """Generate question from template bank (LLM fallback)."""
    # Clarification questions
    if question_type == "clarify" and session.contradictions:
        dim = session.contradictions[0]
        clarify_q = CLARIFY_QUESTIONS.get(dim)
        if clarify_q:
            return clarify_q

    # Follow-up for short answers
    if question_type == "follow_up" and session.answers:
        # Use follow-up template
        idx = len(session.dimension_answers.get(target_dimension, []))
        follow_up = FOLLOW_UP_QUESTIONS[idx % len(FOLLOW_UP_QUESTIONS)]
        return follow_up

    # Standard dimension question from bank
    questions = FALLBACK_QUESTIONS.get(target_dimension, FALLBACK_QUESTIONS["日常生活"])
    # Track which index we're at for this dimension
    key = f"{session.session_id}:{target_dimension}"
    idx = _dimension_question_index.get(key, 0)
    question = questions[idx % len(questions)]
    _dimension_question_index[key] = (idx + 1) % len(questions)

    return question
