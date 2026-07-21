"""Fallback question bank for when LLM is unavailable.

Organized by dimension. Each dimension has ~15 diverse, non-overlapping questions
covering different sub-aspects. Questions within the same dimension are designed to
ask about distinct things to avoid repetition within a session.

Also provides deduplication utilities to prevent asking the same or similar question twice.
"""

import re
from typing import List, Set

# ============================================================
# Expanded question bank (~15 per dimension, 105+ total)
# Each question targets a distinct sub-aspect — no two ask the same thing.
# ============================================================

FALLBACK_QUESTIONS = {
    # --- 记忆 (16 questions, distinct sub-aspects) ---
    "记忆": [
        # 物品遗忘
        "咱们聊聊日常小事。您最近有没有过想找什么东西，一下子想不起来放哪了？",
        "出门的时候，有没有过走到半路突然想起忘了带钥匙或者手机？",
        "平时常用的东西，比如眼镜、遥控器，会不会经常找不到？",
        # 人物/事件记忆
        "您平时记亲戚朋友的名字还顺利吗？有没有见了面一下子叫不出名字？",
        "最近有没有别人跟您说过的事，过两天您就不太记得了？",
        "家里最近有没有发生什么特别的事，您能跟我说说吗？",
        # 近期记忆
        "昨天或者前天吃了什么，您还能想起来吗？",
        "今天早上起来以后做了哪些事，您能按顺序跟我说说吗？",
        # 远期记忆
        "您年轻时候的工作，现在回想起来还清楚吗？",
        "小时候住的地方，您还记得是什么样子吗？",
        # 意图记忆
        "有没有过走进一个房间，突然忘了自己要来干什么？",
        "您有没有话到嘴边突然忘了要说什么的情况？",
        # 重复行为
        "会不会有时候做完一件事，过一会儿又去做一遍，自己没察觉？",
        # 客观观察
        "家里人或者朋友有没有跟您提过，说您记性不如以前了？",
        "您觉得自己记事情，是最近的事容易忘，还是以前的事容易忘？",
        # 补偿策略
        "您平时会不会用笔记、日历或者手机提醒自己要做的事？",
    ],

    # --- 定向 (14 questions) ---
    "定向": [
        # 时间定向
        "您知道今天是星期几吗？大概是几月份了？",
        "不看手机或者钟表的话，您能大概猜出现在是上午还是下午吗？",
        "您知道现在是什么季节吗？",
        # 日期推算
        "如果今天是周三，您知道后天是星期几吗？",
        "今年是哪一年，您能说出来吗？",
        # 地点定向
        "您现在住的这个小区或者街道叫什么名字？",
        "您家附近有什么好认的建筑或者公园吗？从您家走过去大概要多久？",
        "如果要去最近的菜市场或者超市，您知道怎么走吗？",
        # 空间定向
        "您现在是在哪个城市，能告诉我吗？",
        "咱们现在是在您家里聊天，还是在别的地方？",
        # 人物定向
        "您知道我是谁吗？或者您猜我可能是做什么的？",
        "平时跟您聊天最多的人是谁？您跟他是什么关系？",
        # 情境定向
        "您知道咱们今天为什么会聊这些吗？",
        "您平时出门，回家的时候有没有迷路过？",
    ],

    # --- 语言表达 (15 questions) ---
    "语言表达": [
        # 找词困难
        "您平时跟人聊天，有没有想说一个词但一下子想不起来的？这种时候多吗？",
        "跟人说话的时候，会不会用'那个'、'这个东西'来代替想不起来的词？",
        # 表达流畅度
        "您觉得自己说话跟以前比，是更顺畅了还是更容易卡住？",
        "最近有没有说着说着突然不知道说到哪了的情况？",
        # 理解能力
        "平时看电视新闻或者听广播，能听懂里面在说什么吗？",
        "别人跟您说一件事，您一般听一遍能明白吗？还是需要再问一遍？",
        "家里小辈跟您聊天，他们说的内容您能跟上吗？",
        # 阅读
        "您平时看书看报吗？看完一段能说出大概讲了什么吗？",
        "手机上的短信或者微信，您读起来费不费劲？",
        # 书写
        "您现在写字还方便吗？会不会写的时候忘了某个字怎么写？",
        # 复述能力
        "如果别人跟您讲了一个小故事，您能大概复述给别人听吗？",
        # 对话参与
        "跟好几个人一起聊天的时候，您跟得上大家的话题吗？",
        "别人跟您说话，您一般多久能反应过来回答？",
        # 语言丰富度
        "您觉得自己平时说话用的词，跟以前比是多了还是少了？",
        "有没有觉得有些词现在不太会用了，或者用起来不太自然？",
    ],

    # --- 执行能力 (16 questions) ---
    "执行能力": [
        # 家务/烹饪
        "您平时做饭吗？做一顿饭从准备到做好，您觉得应付得来吗？",
        "做菜的时候能同时看好几个锅吗？还是一道一道来？",
        # 财务管理
        "出门买菜或者买东西，算账找钱您觉得还利索吗？",
        "家里的水电费、日常开销，是您在管还是别人帮您管？",
        # 工具使用
        "手机您用得习惯吗？比如打电话、看消息这些基本功能。",
        "家里的电视遥控器、洗衣机这些，您操作起来方便吗？",
        # 计划与组织
        "如果要出门办两三件事，您会提前想好先去哪后去哪吗？",
        "让您安排明天上午要做的事，您会怎么一件一件安排？",
        "有没有想去做什么事，但坐下来想半天不知道怎么开始？",
        # 任务切换
        "正在做一件事的时候，如果突然有别的事要处理，您觉得转得过来吗？",
        # 判断与决策
        "遇到不太熟悉的事，您一般怎么拿主意？是自己想还是问别人？",
        "如果有人打电话说您中奖了要您转钱，您会怎么处理？",
        # 安全注意
        "做完饭您会检查有没有关火关煤气吗？有没有忘记过关火的情况？",
        "出门的时候，您会检查门窗水电有没有关好吗？",
        "您平时自己吃药吗？会不会有时候忘了吃，或者吃重复了？",
        # 学习新事物
        "最近有没有学过什么新东西，比如用新的手机功能、或者学一道新菜？",
    ],

    # --- 情绪 (15 questions) ---
    "情绪": [
        # 总体心境
        "最近心情总体怎么样？是开心的日子多，还是闷闷的日子多？",
        "如果用十分来打分，十分是最开心，您给最近的心情打几分？",
        # 兴趣减退
        "以前喜欢做的事，您现在还喜欢做吗？还有没有那个兴致？",
        "您觉得每天过得有意思吗？有没有什么盼头？",
        # 焦虑/担忧
        "最近有没有让您特别操心或者担心的事？",
        "会不会为了一些小事反复想、放不下？",
        "您担心自己的记性或者身体吗？这种担心多不多？",
        # 烦躁/易怒
        "最近有没有觉得容易着急、火气比以前大？",
        "有没有因为一点小事就跟家里人不高兴的情况？",
        # 孤独感
        "您平时会觉得孤单吗？这种时候多不多？",
        "一个人的时候，您是觉得清静舒服，还是觉得少了点什么？",
        # 睡眠与情绪
        "心情不好的时候，会不会影响睡觉？",
        # 身体与情绪
        "最近有没有觉得浑身没劲、不想动，也不是生病就是提不起精神？",
        # 社会支持
        "有心事的时候，您一般跟谁说？还是自己消化？",
        "您觉得家里人关心您的感受吗？",
    ],

    # --- 睡眠 (15 questions) ---
    "睡眠": [
        # 入睡
        "您晚上一般几点躺下？躺下以后大概多久能睡着？",
        "有没有躺床上半天睡不着的？这种情况多吗？",
        # 时长
        "一晚上大概能睡几个小时？您觉得够不够？",
        "早上一般几点醒？是自然醒还是被闹钟或者别的事叫醒？",
        # 中途醒来
        "夜里中途会醒吗？一般醒几次？",
        "醒了以后还能再睡着吗？还是醒了就睡不着了？",
        # 早醒
        "有没有早上醒得特别早，想再睡又睡不着的？",
        # 白天精神
        "白天精神怎么样？会不会想打瞌睡？",
        "您白天会午睡吗？一般睡多久？",
        # 梦境
        "晚上做梦多吗？做的梦还记得住吗？",
        # 睡眠变化
        "您觉得最近的睡眠跟以前比，是变好了还是变差了？",
        # 睡眠习惯
        "睡前一般做什么？看手机、看电视还是看书？",
        "您睡觉的环境安静吗？有没有什么声音或者光线影响您？",
        # 药物
        "有没有吃帮助睡觉的药或者保健品？",
    ],

    # --- 日常生活 (15 questions) ---
    "日常生活": [
        # 饮食
        "您平时一天三餐规律吗？大概都吃些什么？",
        "胃口怎么样？跟以前比有变化吗？",
        "是自己做饭还是有人做给您吃？",
        # 活动
        "您每天出门吗？一般出去做些什么？",
        "平时有什么固定的活动吗？比如散步、买菜、遛弯。",
        # 家务
        "家务活是自己做还是有人帮忙？哪些事您自己做？",
        # 个人护理
        "洗澡、穿衣这些，您自己来方便吗？",
        # 社交活动
        "平时会跟邻居、朋友串门聊天吗？多久一次？",
        "最近有没有参加过什么集体活动，比如社区活动、广场舞、老年大学？",
        # 生活变化
        "最近这一年，生活上有没有什么大的变化？比如搬家、换人照顾、生过病。",
        # 自我评价
        "您觉得自己现在的生活自理能力跟去年比怎么样？",
        "每天做的事，您觉得充实吗？还是觉得一天挺长的？",
        # 独居/照料
        "您平时一个人住还是跟家人一起？",
        "如果需要帮忙，您第一个会找谁？方便找吗？",
        # 安全
        "您自己出门家里人放心吗？他们有没有担心过您的安全？",
        "最近有没有摔倒过？或者差点摔倒的情况？",
    ],
}

# ============================================================
# Follow-up questions — diverse ways to ask for more detail
# ============================================================
FOLLOW_UP_QUESTIONS = [
    "您能再多说一点吗？比如具体是什么样的？",
    "能给我举个例子吗？这样我能更好地理解。",
    "您刚才提到这件事，能再详细说说吗？",
    "听起来挺有意思的，后来怎么样了呢？",
    "您说的这个情况，大概多久发生一次？",
    "除了刚才说的，还有其他类似的吗？",
    "您说的这些，对您平时生活影响大吗？",
    "家里人或者朋友怎么看这件事？他们有没有说什么？",
    "您觉得这是什么原因造成的呢？",
    "如果跟前两年比，这方面是变好了还是变差了？",
    "这件事让您觉得困扰吗？还是说已经习惯了？",
    "最近有没有因为这件事做了什么改变？",
]

# ============================================================
# Clarification questions — for contradictions
# ============================================================
CLARIFY_QUESTIONS = {
    "记忆": "您前面提到记性还行，但刚才说容易忘事。这两种情况，哪一种更符合您最近的日常状态？",
    "睡眠": "您前面说睡得还可以，后面又提到睡不好。最近这一周整体上睡得怎么样？",
    "情绪": "我注意到您对心情的说法有些不太一样。最近一周，开心和不开心哪一种时间更多？",
    "定向": "您前面说对时间挺清楚的，但后面又有点不确定。平时需要别人提醒您今天星期几吗？",
    "语言表达": "您前面觉得聊天挺顺，但后面又提到有些困难。跟熟人和跟生人聊天，差别大吗？",
    "执行能力": "您前面说做事没问题，后面提到有些事需要帮忙。哪些事您习惯自己来，哪些需要搭把手？",
    "日常生活": "您前面说日子过得挺规律，后来又提到有些变化。最近一周和之前比，哪个更像您的日常？",
}

TOPIC_LABELS = {
    "记忆": "记忆情况",
    "定向": "定向能力",
    "语言表达": "语言表达",
    "执行能力": "执行能力",
    "情绪": "情绪感受",
    "睡眠": "睡眠状况",
    "日常生活": "日常生活",
}

# ============================================================
# Deduplication utilities
# ============================================================

def _normalize(text: str) -> str:
    """Normalize text for similarity comparison: remove punctuation, whitespace."""
    return re.sub(r"[，。！？、,.\s!?\"\"‘'']+", "", text)


def _extract_keywords(text: str) -> Set[str]:
    """Extract meaningful 2-4 character keyword chunks for overlap detection."""
    cleaned = _normalize(text)
    keywords = set()
    for length in (2, 3, 4):
        for i in range(len(cleaned) - length + 1):
            keywords.add(cleaned[i:i + length])
    return keywords


def _similarity(q1: str, q2: str) -> float:
    """Calculate Jaccard similarity between two questions based on keyword overlap.

    Returns 0.0 (completely different) to 1.0 (identical meaning).
    """
    k1 = _extract_keywords(q1)
    k2 = _extract_keywords(q2)
    if not k1 or not k2:
        return 0.0
    intersection = len(k1 & k2)
    union = len(k1 | k2)
    return intersection / union if union > 0 else 0.0


def _is_too_similar(new_question: str, used_questions: List[str], threshold: float = 0.45) -> bool:
    """Check if a question is too similar to any previously asked question."""
    if not used_questions:
        return False
    for used in used_questions:
        if _similarity(new_question, used) >= threshold:
            return True
    return False


def pick_unused_question(
    dimension: str,
    used_questions: List[str],
    exclude_from_pool: bool = True,
) -> str:
    """Pick a question from the dimension bank that hasn't been asked yet.

    Prefers:
    1. Exact match not in used_questions
    2. If all questions are used or too similar, picks the least similar one

    Args:
        dimension: Which dimension to pick from
        used_questions: List of all previously asked question texts
        exclude_from_pool: If True, skip questions already in used_questions

    Returns:
        A question string
    """
    pool = FALLBACK_QUESTIONS.get(dimension, FALLBACK_QUESTIONS["日常生活"])

    # First: try to find an unused, non-similar question
    candidates = []
    for q in pool:
        if exclude_from_pool and q in used_questions:
            continue
        if not _is_too_similar(q, used_questions):
            candidates.append(q)

    if candidates:
        # Pick the first candidate (they're already diverse by design)
        return candidates[0]

    # All questions are either used or too similar — pick least similar
    best_q = pool[0]
    best_sim = 1.0
    for q in pool:
        max_sim = max((_similarity(q, u) for u in used_questions), default=0.0)
        if max_sim < best_sim:
            best_sim = max_sim
            best_q = q

    return best_q


def pick_unused_followup(used_questions: List[str]) -> str:
    """Pick a follow-up question that hasn't been used yet."""
    for q in FOLLOW_UP_QUESTIONS:
        if q not in used_questions:
            return q
    # All used — cycle with least similar
    best_q = FOLLOW_UP_QUESTIONS[0]
    best_sim = 1.0
    for q in FOLLOW_UP_QUESTIONS:
        max_sim = max((_similarity(q, u) for u in used_questions), default=0.0)
        if max_sim < best_sim:
            best_sim = max_sim
            best_q = q
    return best_q
