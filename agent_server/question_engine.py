"""Question generation engine.

Two modes:
1. LLM mode (primary): uses AI to generate natural, context-aware questions
2. Fallback mode: uses expanded template bank with deduplication

All questions are tracked per session to prevent similar-meaning repeats.
Education level is used ONLY to adjust question wording, never for scoring.
"""

from typing import Optional, List
from session_manager import SessionState
from config import (
    DIMENSIONS, INITIAL_DIMENSION_ORDER, MIN_ROUNDS,
    EDUCATION_INSTRUCTIONS, OPENING_MESSAGES,
)
from education_adapter import get_education_level, get_education_instruction
from fallback_topics import (
    FALLBACK_QUESTIONS, FOLLOW_UP_QUESTIONS, CLARIFY_QUESTIONS, TOPIC_LABELS,
    pick_unused_question, pick_unused_followup, _is_too_similar,
)
from coverage_tracker import classify_dimension
from llm_client import get_llm_client


def generate_initial_question(session: SessionState) -> str:
    """Generate the very first question of the screening.

    Records it in session.asked_questions for dedup tracking.
    """
    edu_level = session.education_level
    opening = OPENING_MESSAGES.get(edu_level, OPENING_MESSAGES["secondary_low"])
    session.asked_questions.append(opening)
    return opening


def generate_next_question(
    session: SessionState,
    target_dimension: str,
    llm_available: bool = True,
) -> str:
    """Generate the next question for the given dimension.

    Uses deduplication to ensure no similar question is asked twice.
    The generated question is automatically recorded in session.asked_questions.
    """
    question_type = _determine_question_type(session)
    asked = session.asked_questions

    if llm_available:
        try:
            q = _generate_llm_question(session, target_dimension, question_type, asked)
            q = _ensure_respectful_followup(q, session, asked)
            session.asked_questions.append(q)
            return q
        except Exception:
            pass

    # Fallback: use expanded template bank with dedup
    q = _generate_fallback_question(session, target_dimension, question_type, asked)
    q = _ensure_respectful_followup(q, session, asked)
    session.asked_questions.append(q)
    return q


def _ensure_respectful_followup(question: str, session: SessionState, asked_questions: List[str]) -> str:
    """Keep short-answer follow-ups neutral and relevant to the previous question."""
    if not session.answers:
        return question

    answer = session.answers[-1].get("text", "").strip()
    previous = asked_questions[-1] if asked_questions else ""
    short_affirmative = answer in {"有", "有过", "是", "对", "会", "偶尔", "有一点", "有时候"}
    inappropriate = "挺有意思" in question or "有意思的，后来" in question
    if not short_affirmative and not inappropriate:
        return question

    if any(word in previous for word in ("找不到", "放哪", "忘", "想不起来", "记不清")):
        return "我明白了。最近一次是什么时候？后来是自己想起来了，还是家里人提醒您的？"
    if any(word in previous for word in ("睡", "醒", "失眠", "做梦")):
        return "我明白了。这种情况最近一周大概会有几次？"
    if any(word in previous for word in ("心情", "担心", "操心", "孤单", "着急")):
        return "我明白了。这样的感受最近常出现吗？"
    if any(word in previous for word in ("说不出来", "想不起词", "聊天", "表达")):
        return "我明白了。最近一次出现这种情况时，后来是自己想起来的吗？"
    if any(word in previous for word in ("做饭", "家务", "算账", "手机", "安排", "关火")):
        return "我明白了。遇到这种情况时，通常需要家里人帮忙吗？"
    return "我明白了。您愿意说说最近一次是什么情况吗？"


def _determine_question_type(session: SessionState) -> str:
    """Determine what kind of question to ask next.

    Returns: "continue" | "follow_up" | "clarify"
    """
    if not session.answers:
        return "continue"

    last = session.answers[-1]

    if session.contradictions and session.round >= MIN_ROUNDS:
        return "clarify"

    if last.get("length", len(last.get("text", ""))) <= 20:
        return "follow_up"

    dim = last.get("dimension", "")
    if dim and len(session.dimension_answers.get(dim, [])) >= 2:
        return "follow_up"

    return "continue"


def _generate_llm_question(
    session: SessionState,
    target_dimension: str,
    question_type: str,
    asked_questions: List[str],
) -> str:
    """Generate question using LLM API, with dedup instructions."""
    client = get_llm_client()
    if client is None:
        raise Exception("LLM client not configured")

    education_instruction = get_education_instruction(session.education_level)
    answer_summary = _build_answer_summary(session)
    dim_answers = _build_dimension_answer_summary(session, target_dimension)

    # Build list of already-asked questions for the LLM to avoid
    asked_list = "\n".join(f"- {q}" for q in asked_questions[-15:])  # last 15 for context
    dedup_instruction = (
        "重要：以下是你在这场对话中已经问过的问题，"
        "新问题必须与这些问题完全不同，不能换一种说法问同一件事。\n"
        f"{asked_list}\n"
    )

    type_instruction = {
        "continue": "自然地过渡到新话题，问题要像日常聊天一样。问一个你还没问过的具体方面。",
        "follow_up": (
            "针对这个维度进行深入追问。问题要具体，引导用户给出更多细节。"
            "不要让对方觉得你在质疑或测试他。问的角度要和之前不一样。"
        ),
        "clarify": (
            "温和地请用户澄清之前说法中不太一致的地方。"
            "不要直接说你前后矛盾，而是自然地再问一次，给用户重新表达的机会。"
        ),
    }.get(question_type, "")

    system_prompt = (
        "你是一位温和、耐心的认知健康筛查对话助手，正在与一位老年人进行日常聊天。"
        "你的任务是自然地引导对话，了解老年人在七个方面的日常表现："
        "记忆、定向、语言表达、执行能力、情绪、睡眠、日常生活。"
        "\n\n"
        "重要原则：\n"
        "1. 永远不要提及测试、评估、筛查、诊断等词\n"
        "2. 问题要像家人朋友聊天一样自然\n"
        "3. 一次只问一个问题或一个主题\n"
        "4. 尊重对方，用您称呼\n"
        "5. 不要评判对方的回答\n"
        "6. 每个问题都必须和之前的完全不同，避免重复问相似的内容\n"
        "7. 每次只输出问题本身，不要加任何说明或前缀"
    )

    user_prompt = (
        f"当前是第 {session.round + 1} 轮对话。\n\n"
        f"目标维度：{target_dimension}\n"
        f"问题类型：{question_type}\n\n"
        f"教育背景适配要求：{education_instruction}\n\n"
        f"用户之前回答的维度总结：\n{answer_summary}\n\n"
        f"在「{target_dimension}」方面，用户之前说过：\n{dim_answers}\n\n"
        f"{dedup_instruction}\n"
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
    asked_questions: List[str],
) -> str:
    """Generate question from expanded template bank with deduplication.

    Uses pick_unused_question() which selects questions that:
    1. Have not been asked before (exact match)
    2. Are not too similar (keyword overlap < 45%) to any asked question
    3. Falls back to least-similar question if all are used
    """
    # Clarification: use dedicated clarification question (one per dimension)
    if question_type == "clarify" and session.contradictions:
        dim = session.contradictions[0]
        clarify_q = CLARIFY_QUESTIONS.get(dim)
        if clarify_q and clarify_q not in asked_questions:
            return clarify_q
        # Fall through to regular question if clarify already used

    # Follow-up for short answers or revisiting
    if question_type == "follow_up":
        # Try a fresh follow-up question first
        fu = pick_unused_followup(asked_questions)
        if fu:
            return fu
        # If all follow-ups used, pick a new dimension question
        pass

    # Standard: pick an unused, non-similar question from the bank
    question = pick_unused_question(target_dimension, asked_questions)
    return question
