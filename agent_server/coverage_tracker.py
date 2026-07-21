"""Coverage and confidence calculation for adaptive screening."""

from typing import Dict, List, Tuple
from session_manager import SessionState
from config import (
    DIMENSIONS, DIMENSION_KEYWORDS,
    SHORT_ANSWER_CHARS, GOOD_ANSWER_CHARS,
    MAX_ROUNDS, MIN_ROUNDS,
)


def classify_dimension(text: str, current_dimension: str = "") -> str:
    """Classify which dimension an answer belongs to based on keyword matching.

    Returns the most likely dimension name, or current_dimension/default if unclear.
    """
    if not text.strip():
        return current_dimension or "日常生活"

    scores: Dict[str, int] = {}
    for dim, keywords in DIMENSION_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw in text:
                score += 1
        scores[dim] = score

    # Find max scoring dimension
    max_score = max(scores.values()) if scores else 0
    if max_score == 0:
        return current_dimension or "日常生活"

    # Return the dimension with highest keyword match
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else (current_dimension or "日常生活")


def calculate_coverage(session: SessionState) -> float:
    """Calculate how well the 7 dimensions are covered (0.0 to 1.0).

    Each dimension needs at least 2 answers for full coverage.
    A round bonus is applied for rounds beyond MIN_ROUNDS.
    """
    if not session.answers:
        return 0.0

    total_weight = 0.0
    for dim in DIMENSIONS:
        count = len(session.dimension_answers.get(dim, []))
        if count >= 3:
            total_weight += 1.0
        elif count == 2:
            total_weight += 0.8
        elif count == 1:
            total_weight += 0.5
        # count == 0: weight += 0.0

    base_coverage = total_weight / len(DIMENSIONS)

    # Bonus for rounds beyond minimum (more data = richer coverage)
    if session.round > MIN_ROUNDS:
        round_bonus = min(0.15, (session.round - MIN_ROUNDS) * 0.03)
    else:
        round_bonus = 0.0

    return round(min(1.0, base_coverage + round_bonus), 2)


def calculate_confidence(session: SessionState) -> float:
    """Calculate confidence in the assessment so far (0.0 to 1.0).

    Based on: answer length, dimension balance, round count,
    score stability, and contradiction penalties.
    """
    if not session.answers:
        return 0.0

    # 1. Average answer length score (longer answers → more informative)
    avg_len = sum(a.get("length", len(a["text"])) for a in session.answers)
    avg_len /= len(session.answers)
    len_score = min(1.0, avg_len / GOOD_ANSWER_CHARS)

    # 2. Dimension balance: how many dimensions have adequate coverage
    dim_balance = sum(
        1 for d in DIMENSIONS
        if len(session.dimension_answers.get(d, [])) >= 2
    ) / len(DIMENSIONS)

    # 3. Round progress (more rounds → more data)
    round_score = min(1.0, session.round / MAX_ROUNDS * 1.2)

    # 4. Stability bonus
    stability_bonus = 0.10 if _is_result_stable(session) else 0.0

    # 5. Contradiction penalty (each contradiction reduces confidence)
    contra_count = len(session.contradictions) if hasattr(session, 'contradictions') else 0
    contra_penalty = min(0.20, contra_count * 0.08)

    raw = (
        len_score * 0.25 +
        dim_balance * 0.30 +
        round_score * 0.20 +
        stability_bonus * 0.15 -
        contra_penalty * 0.10
    )

    return round(max(0.10, min(1.0, raw)), 2)


def _is_result_stable(session: SessionState) -> bool:
    """Check if dimension scores have stabilized over recent rounds.

    Returns True if the last 3 score vectors have low variance.
    """
    history = session.score_history
    if len(history) < 3:
        return False

    recent = history[-3:]
    # Calculate per-dimension variance across last 3 rounds
    total_variance = 0.0
    for dim in DIMENSIONS:
        values = [h.get(dim, 0.0) for h in recent]
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        total_variance += variance

    avg_variance = total_variance / len(DIMENSIONS)
    return avg_variance < 0.025  # Threshold for "stable"


def detect_contradictions(session: SessionState) -> List[str]:
    """Detect contradictory statements across answers within the same dimension.

    Uses simple positive/negative keyword shift detection.
    Returns list of dimension names where contradictions were found.
    """
    contradictions = []

    for dim in DIMENSIONS:
        answers = session.dimension_answers.get(dim, [])
        if len(answers) < 2:
            continue

        texts = [a["text"] for a in answers]

        # Positive sentiment keywords for this dimension
        positive_kw = {
            "记忆": ["记得", "记住", "没问题", "还可以", "还行", "不错"],
            "睡眠": ["睡得好", "睡得着", "安稳", "还可以", "不错", "没问题"],
            "情绪": ["开心", "高兴", "不错", "还行", "挺好", "没问题"],
            "定向": ["知道", "清楚", "没问题", "还行"],
            "语言表达": ["顺畅", "没问题", "还行", "没问题"],
            "执行能力": ["能做", "没问题", "还行", "自己做"],
            "日常生活": ["规律", "没问题", "还行", "正常", "自己做"],
        }
        # Negative sentiment keywords
        negative_kw = {
            "记忆": ["记不住", "忘了", "忘事", "总是忘", "不记得", "记不清"],
            "睡眠": ["睡不着", "失眠", "睡不好", "总是醒", "睡不踏实"],
            "情绪": ["不开心", "难过", "烦躁", "担心", "没意思"],
            "定向": ["不知道", "分不清", "迷路", "走丢"],
            "语言表达": ["说不出来", "表达不好", "跟不上"],
            "执行能力": ["不会", "做不了", "没办法", "需要帮忙"],
            "日常生活": ["不规律", "没胃口", "不想动", "不出门"],
        }

        pos_kw = positive_kw.get(dim, ["好", "没问题"])
        neg_kw = negative_kw.get(dim, ["不好", "不行"])

        # Check if both positive and negative keywords appear across answers
        has_positive = any(any(kw in t for kw in pos_kw) for t in texts)
        has_negative = any(any(kw in t for kw in neg_kw) for t in texts)

        if has_positive and has_negative:
            # Check they're not in the same answer (which would be nuanced/normal)
            same_answer = any(
                any(kw in t for kw in pos_kw) and any(kw in t for kw in neg_kw)
                for t in texts
            )
            if not same_answer:
                contradictions.append(dim)

    session.contradictions = contradictions
    return contradictions


def get_weakest_dimensions(session: SessionState) -> List[str]:
    """Return dimensions sorted by coverage weakness (least covered first)."""
    dim_scores = []
    for dim in DIMENSIONS:
        count = len(session.dimension_answers.get(dim, []))
        score = session.dimension_scores.get(dim, 0.0)
        # Weight: fewer answers AND lower score = weaker
        weakness = (3 - min(count, 3)) / 3 * 0.5 + (1.0 - score) * 0.5
        dim_scores.append((dim, weakness))

    dim_scores.sort(key=lambda x: x[1], reverse=True)
    return [d[0] for d in dim_scores if d[1] > 0.3]
