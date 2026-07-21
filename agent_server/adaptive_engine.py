"""Core adaptive continuation algorithm.

Decides whether screening should continue or stop based on:
- coverage (information sufficiency across 7 dimensions)
- confidence (answer stability and quality)
- contradictions detected
- round count (min/max boundaries)
"""

from typing import Tuple, Optional
from session_manager import SessionState
from coverage_tracker import (
    calculate_coverage, calculate_confidence,
    detect_contradictions, get_weakest_dimensions,
)
from config import (
    MIN_ROUNDS, MAX_ROUNDS,
    COVERAGE_STOP_THRESHOLD, CONFIDENCE_STOP_THRESHOLD,
    DIMENSION_LOW_THRESHOLD, SHORT_ANSWER_CHARS,
    DIMENSIONS, INITIAL_DIMENSION_ORDER,
)


def should_continue(session: SessionState) -> Tuple[bool, str, float, float]:
    """Decide whether to continue or stop screening.

    Returns: (should_continue, reason, coverage, confidence)
    """
    current_round = session.round

    # Recalculate coverage and confidence
    coverage = calculate_coverage(session)
    confidence = calculate_confidence(session)
    session.coverage = coverage
    session.confidence = confidence

    # --- HARD BOUNDARY: force end at MAX_ROUNDS ---
    if current_round >= MAX_ROUNDS:
        session.forced_end = True
        return (
            False,
            "已达到最大评估轮数，部分信息仍需进一步确认",
            coverage,
            confidence,
        )

    # --- Before MIN_ROUNDS: always continue ---
    if current_round < MIN_ROUNDS:
        # Check which dimensions are still uncovered
        uncovered = [
            d for d in DIMENSIONS
            if len(session.dimension_answers.get(d, [])) == 0
        ]
        if uncovered:
            reason = f"{'、'.join(uncovered[:2])}维度的信息还未覆盖"
        else:
            remaining = MIN_ROUNDS - current_round
            reason = f"还需完成至少 {remaining} 轮基础评估"
        return (True, reason, coverage, confidence)

    # --- Round 10+: evaluate information adequacy ---
    # 1. Check stop conditions: good coverage + high confidence + stable
    if coverage >= COVERAGE_STOP_THRESHOLD and confidence >= CONFIDENCE_STOP_THRESHOLD:
        if _is_stable_across_rounds(session) and not detect_contradictions(session):
            return (
                False,
                "信息已充分，评估结果稳定，可以自然结束",
                coverage,
                confidence,
            )

    # 2. Check for short/vague last answer → follow up
    if session.answers:
        last = session.answers[-1]
        if last.get("length", len(last["text"])) <= SHORT_ANSWER_CHARS:
            dim = last.get("dimension", "日常生活")
            return (
                True,
                f"{dim}方面的信息还不够详细，想再多了解一下",
                coverage,
                confidence,
            )

    # 3. Check for contradictions → clarify
    contradictions = detect_contradictions(session)
    if contradictions:
        return (
            True,
            f"注意到{contradictions[0]}方面前后的说法有些不一样，想再确认一下",
            coverage,
            confidence,
        )

    # 4. Check dimensions with low coverage → follow up weak areas
    weak_dims = [
        d for d in DIMENSIONS
        if (
            len(session.dimension_answers.get(d, [])) <= 1 and
            session.dimension_scores.get(d, 0.0) < DIMENSION_LOW_THRESHOLD
        )
    ]
    if weak_dims:
        return (
            True,
            f"{'、'.join(weak_dims[:2])}方面的信息还可以再补充一些",
            coverage,
            confidence,
        )

    # 5. If coverage or confidence still sub-threshold → continue
    if coverage < 0.70 or confidence < 0.60:
        return (
            True,
            "信息仍在完善中，继续收集更多内容",
            coverage,
            confidence,
        )

    # 6. Natural end: everything looks good
    return (
        False,
        "评估信息已充分，结果稳定，可以自然结束",
        coverage,
        confidence,
    )


def _is_stable_across_rounds(session: SessionState) -> bool:
    """Check if dimension scores are stable over recent rounds.

    Requires at least 2 consecutive rounds without new contradictions
    and with consistent dimension scores.
    """
    history = session.score_history
    if len(history) < 3:
        return False

    # Check recent score stability
    recent = history[-3:]
    total_variance = 0.0
    for dim in DIMENSIONS:
        values = [h.get(dim, 0.0) for h in recent]
        if all(v == 0.0 for v in values):
            continue
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        total_variance += variance

    avg_variance = total_variance / max(1, len([d for d in DIMENSIONS
        if any(h.get(d, 0.0) > 0 for h in recent)]))
    return avg_variance < 0.03


def select_next_dimension(session: SessionState) -> str:
    """Select which dimension to ask about next.

    Priority:
    1. For rounds 1-7: follow INITIAL_DIMENSION_ORDER
    2. For rounds 8+: pick weakest covered dimension
    3. For rounds 10+: prioritize dimensions with contradictions
    """
    current_round = session.round

    # Rounds 1-7: systematic coverage
    if current_round < len(INITIAL_DIMENSION_ORDER):
        return INITIAL_DIMENSION_ORDER[current_round]

    # Rounds 8-9: cover any missed dimensions
    if current_round < MIN_ROUNDS:
        uncovered = [
            d for d in DIMENSIONS
            if len(session.dimension_answers.get(d, [])) == 0
        ]
        if uncovered:
            return uncovered[0]
        # All covered at least once, ask the one with fewest answers
        return min(DIMENSIONS, key=lambda d: len(session.dimension_answers.get(d, [])))

    # Round 10+: adaptive selection
    # Priority 1: dimension with contradictions
    if session.contradictions:
        return session.contradictions[0]

    # Priority 2: weakest dimension (least covered or lowest score)
    weakest = get_weakest_dimensions(session)
    if weakest:
        return weakest[0]

    # Priority 3: dimension with fewest answers
    return min(DIMENSIONS, key=lambda d: len(session.dimension_answers.get(d, [])))
