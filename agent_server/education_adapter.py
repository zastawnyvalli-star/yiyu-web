"""Education-based question adaptation.

Education ONLY adjusts question wording and task difficulty.
It MUST NOT affect risk scoring — scoring and question generation are separate concerns.
"""

from config import EDUCATION_INSTRUCTIONS, EDUCATION_LEVEL_MAP


def get_education_level(education_raw: str) -> str:
    """Map raw education string to internal level key."""
    return EDUCATION_LEVEL_MAP.get(education_raw, "secondary_low")


def get_education_instruction(education_level: str) -> str:
    """Get the prompt instruction for LLM question generation based on education."""
    return EDUCATION_INSTRUCTIONS.get(education_level, EDUCATION_INSTRUCTIONS["secondary_low"])


def adapt_question_for_education(question: str, education_level: str) -> str:
    """Post-process a generated question to match education level constraints.

    This is a rule-based fallback simplifier. In LLM mode, the instruction
    is injected into the prompt directly for better results.
    """
    if education_level == "basic":
        # Simplify: shorter sentences, remove idioms
        # Split on Chinese punctuation and take shorter sentences
        parts = question.replace("？", "？\n").replace("。", "。\n").split("\n")
        parts = [p.strip() for p in parts if p.strip()]
        # Keep only first substantive part for basic level
        if len(parts) > 1 and len(parts[0]) > 40:
            # If first part is long, try to shorten
            return parts[0][:40].rsplit("，", 1)[0] + "？" if "？" not in parts[0][:40] else parts[0][:45]
        return question

    return question


def education_note_for_report(education_raw: str) -> dict:
    """Generate the education adaptation note for the final report.

    This is displayed separately from cognitive scores to make clear
    that education affects question style, NOT the risk assessment.
    """
    level = get_education_level(education_raw)

    notes = {
        "basic": {
            "level": education_raw,
            "adaptation": "简化表达、短句为主，一次只问一件事",
            "note": "本次问题表达已根据教育背景做简化适配。"
                    "评分基于语言自然特征，不受教育程度直接影响。"
        },
        "secondary_low": {
            "level": education_raw,
            "adaptation": "使用日常生活场景，避免复杂术语",
            "note": "本次问题表达已根据教育背景做场景适配。"
                    "评分基于语言自然特征，不受教育程度直接影响。"
        },
        "secondary_high": {
            "level": education_raw,
            "adaptation": "日常对话风格，包含简单顺序描述",
            "note": "本次问题表达已根据教育背景做适度适配。"
                    "评分基于语言自然特征，不受教育程度直接影响。"
        },
        "college": {
            "level": education_raw,
            "adaptation": "常规对话风格，可包含归纳和计划类问题",
            "note": "本次问题表达已根据教育背景做适度适配。"
                    "评分基于语言自然特征，不受教育程度直接影响。"
        },
        "university": {
            "level": education_raw,
            "adaptation": "较丰富表达，可包含复述、归纳和计划类问题",
            "note": "本次问题表达已根据教育背景做适度适配。"
                    "评分基于语言自然特征，不受教育程度直接影响。"
        },
    }

    return notes.get(level, notes["secondary_low"])
