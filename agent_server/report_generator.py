"""Report generation for the adaptive screening system.

Produces a report object compatible with the frontend's expected format,
enhanced with adaptive screening metadata.
"""

from typing import Dict, Any, List
from session_manager import SessionState
from config import DIMENSIONS, MAX_ROUNDS
from education_adapter import education_note_for_report


def generate_report(session: SessionState) -> Dict[str, Any]:
    """Generate a complete screening report from session data.

    The report structure matches what the frontend's mergeAgentReport()
    and renderReport() expect, plus adaptive screening metadata.
    """
    answers = session.answers
    if not answers:
        return _empty_report(session)

    # Combine all answer texts for analysis
    all_text = " ".join(a["text"] for a in answers)
    n = len(all_text.replace(" ", ""))

    # Basic text metrics
    sentences = [s for s in all_text.replace("!", "。").replace("?", "？").replace(";", "；").split("。") if s.strip()]
    sent_count = max(1, len(sentences))
    avg_len = n / sent_count

    # Simple keyword-based analysis (mirrors frontend makeReport patterns)
    forget = _count(all_text, "忘|记不清|想不起来|找不到|找不见|重复|糊涂")
    vague = _count(all_text, "那个|这个|东西|什么来着|反正|差不多")
    hes = _count(all_text, "嗯|呃|啊|唉|不知道")
    time_words = _count(all_text, "早上|中午|晚上|昨天|今天|最近|以前|点|分钟|后来|然后")
    detail = min(1.2, len([a for a in answers if len(a["text"]) >= 25]) * 0.12)
    daily_risk = _count(all_text, "迷路|走丢|不会|做饭|关火|煤气|钱|付款|买菜|手机|路线|回家")
    repeat_risk = _count(all_text, "刚说|刚做|反复|重复问|重复说|转头就忘")
    clear_place = _count(all_text, "家里|客厅|卧室|厨房|医院|超市|小区|路上")
    emotion_words = _count(all_text, "烦|急|担心|害怕|紧张|难受")

    # Sub-dimension scores (1-10 scale)
    s = {
        "tipOfTongue": _clamp(8.0 - vague * 0.4 - hes * 0.2 + detail),
        "lexicalComplexity": _clamp(5.8 + min(3, n / 150) - vague * 0.25),
        "wordPhraseRatio": _clamp(6.2 + min(2.2, n / 180) - vague * 0.2),
        "syntacticComplexity": _clamp(5.5 + min(2.5, avg_len / 18) + detail * 0.5),
        "complexThought": _clamp(6.2 + detail + time_words * 0.08 - forget * 0.25 - daily_risk * 0.22),
        "grammaticalAccuracy": _clamp(7.5 - hes * 0.18 + detail * 0.3),
        "semanticDensity": _clamp(6.2 + min(2, n / 200) + clear_place * 0.08 - vague * 0.22),
        "semanticCoherence": _clamp(7.3 + time_words * 0.05 + detail * 0.2 - forget * 0.34 - hes * 0.12),
        "memoryIssues": _clamp(8.3 - forget * 0.62 - repeat_risk * 0.45 - daily_risk * 0.25 - _count(all_text, "不知道|不记得") * 0.42),
    }

    # Dimension composites
    dim = {
        "vocabulary": {
            "tipOfTongue": s["tipOfTongue"],
            "lexicalComplexity": s["lexicalComplexity"],
            "wordPhraseRatio": s["wordPhraseRatio"],
            "compositeScore": _round((s["tipOfTongue"] + s["lexicalComplexity"] + s["wordPhraseRatio"]) / 3),
        },
        "syntax": {
            "syntacticComplexity": s["syntacticComplexity"],
            "complexThought": s["complexThought"],
            "grammaticalAccuracy": s["grammaticalAccuracy"],
            "compositeScore": _round((s["syntacticComplexity"] + s["complexThought"] + s["grammaticalAccuracy"]) / 3),
        },
        "semantic": {
            "semanticDensity": s["semanticDensity"],
            "semanticCoherence": s["semanticCoherence"],
            "memoryIssues": s["memoryIssues"],
            "compositeScore": _round((s["semanticDensity"] + s["semanticCoherence"] + s["memoryIssues"]) / 3),
        },
    }

    # Weighted score
    rule_score = _round(dim["vocabulary"]["compositeScore"] * 0.3 + dim["syntax"]["compositeScore"] * 0.3 + dim["semantic"]["compositeScore"] * 0.4)
    semantic_score = _clamp(7.1 + detail + min(1.1, n / 260) + time_words * 0.05 + clear_place * 0.08 - forget * 0.42 - repeat_risk * 0.5 - daily_risk * 0.38 - vague * 0.16 - emotion_words * 0.08)
    sample_confidence = max(0.45, min(1, (len(answers) / 10 * 0.45) + (min(n, 260) / 260 * 0.35) + (len([a for a in answers if len(a["text"]) >= 18]) / max(1, len(answers)) * 0.2) - hes * 0.025 - vague * 0.018))
    confidence_score = _round(4 + sample_confidence * 6)
    risk_penalty = min(2.2, max(0, forget - 1) * 0.12 + repeat_risk * 0.25 + daily_risk * 0.28 + _count(all_text, "迷路|走丢|关火|煤气") * 0.5)
    good_bonus = min(0.45, detail * 0.14 + time_words * 0.025 + clear_place * 0.025)
    weighted_score = _clamp(rule_score * 0.5 + semantic_score * 0.35 + confidence_score * 0.15 - risk_penalty + good_bonus)

    # Classification
    classification = "normal" if weighted_score >= 7 else ("attention" if weighted_score >= 4 else "suspected_mci")

    # Sub-scores for display
    subs = [
        {"key": "tipOfTongue", "score": s["tipOfTongue"], "name": "舌尖现象", "desc": "找词困难程度"},
        {"key": "lexicalComplexity", "score": s["lexicalComplexity"], "name": "词汇复杂性", "desc": "词汇多样性与深度"},
        {"key": "wordPhraseRatio", "score": s["wordPhraseRatio"], "name": "词比与短语比", "desc": "语言信息密度"},
        {"key": "syntacticComplexity", "score": s["syntacticComplexity"], "name": "句法复杂性", "desc": "句子结构复杂度"},
        {"key": "complexThought", "score": s["complexThought"], "name": "处理复杂思想", "desc": "多步骤推理能力"},
        {"key": "grammaticalAccuracy", "score": s["grammaticalAccuracy"], "name": "语法正确性", "desc": "语法错误频率"},
        {"key": "semanticDensity", "score": s["semanticDensity"], "name": "语义密度", "desc": "内容信息丰富度"},
        {"key": "semanticCoherence", "score": s["semanticCoherence"], "name": "语义连贯性", "desc": "逻辑与话题衔接"},
        {"key": "memoryIssues", "score": s["memoryIssues"], "name": "记忆问题", "desc": "重复与遗忘程度"},
    ]

    # Observations
    obs = [
        f"本次完成 {len(answers)} 轮对话，语言样本约 {n} 字。分数越高，代表当前状态越好。",
        f"信息覆盖度：{session.coverage:.0%}，评估可信度：{session.confidence:.0%}。",
        "多数回答包含较完整叙述，句子长度和信息量较好。" if avg_len >= 18 else "部分回答较短，建议结合更多日常语音样本继续观察。",
        "回答中出现忘事、找物或重复相关线索，建议家属平和地留意频率。" if forget + repeat_risk > 0 else "未观察到明显高频重复提问。",
        "本次样本可信度较好，评分参考性相对更高。" if sample_confidence >= 0.72 else "本次样本量或清晰度一般，分数应结合后续复查一起看。",
    ]

    # Add forced end note if applicable
    if session.forced_end:
        obs.insert(1, "注意：本次筛查达到最大轮数（20轮），部分信息仍需进一步确认，建议定期复查。")

    # Suggestions by classification
    tips = {
        "normal": [
            "继续保持规律作息与有氧运动，维护大脑活力。",
            "坚持社交活动，通过沟通保持语言敏锐度。",
        ],
        "attention": [
            "增加脑力训练，如拼图、阅读或简单计算。",
            "家属记录忘事、重复提问、表达变慢等情况。",
            "1到3个月内复查，必要时咨询记忆门诊。",
        ],
        "suspected_mci": [
            "尽快前往记忆门诊或神经内科获得专业评估。",
            "启动专业指导下的认知康复训练。",
            "家属加强日常看护，优化居家环境。",
        ],
    }.get(classification, [])

    # Education note (separate from cognitive scoring)
    edu_raw = session.profile.get("education", "初中") if session.profile else "初中"
    edu_note = education_note_for_report(edu_raw)

    # Build report object
    report = {
        "id": "r" + str(int(session.created_at * 1000)),
        "createdAt": _iso_date(),
        "date": _local_date(),
        "weightedScore": _round(weighted_score),
        "classification": classification,
        "dim": dim,
        "subs": subs,
        "scoring": {
            "ruleScore": _round(rule_score),
            "semanticScore": _round(semantic_score),
            "confidenceScore": _round(confidence_score),
            "sampleConfidence": _round(sample_confidence * 10),
            "riskPenalty": _round(risk_penalty),
        },
        "obs": obs,
        "tips": tips,
        # Adaptive screening metadata
        "roundsCompleted": len(answers),
        "coverage": session.coverage,
        "confidence": session.confidence,
        "forcedEnd": session.forced_end,
        # Education adaptation note (separate from scores)
        "educationFit": edu_note,
        # For compatibility with frontend mergeAgentReport
        "observations": obs,
        "suggestions": tips,
        "summary": "",
        "disclaimer": "本评估仅作为潜在MCI的初始筛查参考，不提供正式医学诊断。",
        "recommendMedicalConsultation": classification != "normal",
    }

    return report


def _empty_report(session: SessionState) -> Dict[str, Any]:
    """Generate a minimal report when no answers exist."""
    return {
        "id": "r" + str(int(session.created_at * 1000)),
        "createdAt": _iso_date(),
        "date": _local_date(),
        "weightedScore": 0,
        "classification": "attention",
        "dim": {},
        "subs": [],
        "obs": ["本次筛查未收集到足够的回答，建议重新进行。如果多次出现此问题，请联系技术支持。"],
        "tips": ["请重新开始一次新的筛查。"],
        "roundsCompleted": 0,
        "coverage": 0.0,
        "confidence": 0.0,
        "forcedEnd": False,
        "observations": ["本次筛查未收集到足够的回答。"],
        "suggestions": ["请重新开始一次新的筛查。"],
        "summary": "",
        "disclaimer": "本评估仅作为潜在MCI的初始筛查参考，不提供正式医学诊断。",
        "recommendMedicalConsultation": False,
    }


def _count(text: str, pattern: str) -> int:
    """Count regex pattern matches in text."""
    import re
    return len(re.findall(pattern, text))


def _clamp(v: float) -> float:
    """Clamp to [1, 10] range, rounded to 1 decimal."""
    return _round(max(1.0, min(10.0, v)))


def _round(v: float) -> float:
    """Round to 1 decimal place."""
    return round(v * 10) / 10


def _iso_date() -> str:
    """ISO format datetime string."""
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat()


def _local_date() -> str:
    """Local date string in Chinese format."""
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y年%m月%d日")
