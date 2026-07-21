"""Configuration and constants for the adaptive screening agent."""

# Seven assessment dimensions (in priority order for initial coverage)
DIMENSIONS = ["记忆", "定向", "语言表达", "执行能力", "情绪", "睡眠", "日常生活"]

# Initial dimension order for rounds 1-7: cover each dimension once
INITIAL_DIMENSION_ORDER = [
    "日常生活",  # round 1 - easiest, warm-up
    "睡眠",      # round 2
    "情绪",      # round 3
    "记忆",      # round 4
    "定向",      # round 5
    "语言表达",  # round 6
    "执行能力",  # round 7
]

# Round limits
MIN_ROUNDS = 10
MAX_ROUNDS = 20
TYPICAL_MAX_ROUNDS = 16  # Suggested typical completion

# Coverage thresholds
COVERAGE_STOP_THRESHOLD = 0.75   # coverage >= this -> may stop
CONFIDENCE_STOP_THRESHOLD = 0.70 # confidence >= this -> may stop
STABLE_ROUNDS_REQUIRED = 2       # consecutive stable rounds needed
DIMENSION_LOW_THRESHOLD = 0.5    # coverage < this -> follow up

# Answer quality thresholds
SHORT_ANSWER_CHARS = 15  # answers <= this are too short
GOOD_ANSWER_CHARS = 40   # answers >= this are good

# Dimension keywords for classification
DIMENSION_KEYWORDS = {
    "记忆": [
        "忘", "记不清", "想不起来", "找不到", "找不见", "记住", "记得",
        "回忆", "提醒", "备忘录", "记性", "丢三落四", "忘了", "不记得",
        "重复", "反复", "转头就忘", "刚说", "刚做",
    ],
    "定向": [
        "今天", "星期", "几号", "几月", "年份", "时间", "几点",
        "哪里", "什么地方", "迷路", "走丢", "方向", "找不到路",
        "手机看时间", "日历", "钟表", "手表",
    ],
    "语言表达": [
        "说不出来", "想不起词", "那个", "这个", "东西", "什么来着",
        "表达", "说话", "聊天", "交流", "听不懂", "跟不上",
        "看书", "读报", "电视", "新闻",
    ],
    "执行能力": [
        "做饭", "做菜", "家务", "打扫", "收拾", "洗衣",
        "买菜", "付钱", "算账", "找钱", "手机", "遥控器",
        "安排", "计划", "顺序", "先后", "步骤", "怎么办",
        "出门", "办事", "关火", "关煤气", "锁门",
    ],
    "情绪": [
        "开心", "高兴", "难过", "伤心", "烦", "烦躁", "着急",
        "担心", "害怕", "紧张", "闷", "没意思", "无聊",
        "生气", "发火", "哭", "笑", "心情", "情绪",
    ],
    "睡眠": [
        "睡", "觉", "醒", "做梦", "失眠", "熬夜", "早起",
        "午睡", "打瞌睡", "困", "精神", "累", "休息",
        "半夜", "入睡", "睡不着", "睡不好", "安眠药",
    ],
    "日常生活": [
        "吃饭", "喝水", "穿衣", "洗漱", "洗澡", "上厕所",
        "散步", "锻炼", "运动", "买菜", "做饭", "看电视",
        "出门", "串门", "遛弯", "逛", "公园", "超市",
        "吃药", "看病", "体检",
    ],
}

# Education level mappings
EDUCATION_LEVEL_MAP = {
    "小学及以下": "basic",
    "初中": "secondary_low",
    "高中/中专": "secondary_high",
    "大专": "college",
    "本科及以上": "university",
}

# Education-based question adaptation instructions
EDUCATION_INSTRUCTIONS = {
    "basic": (
        "使用简短句子，一次只问一件事。"
        "用最简单、最日常的词。不要使用成语。"
        "不要涉及数字计算或复杂推理。"
    ),
    "secondary_low": (
        "使用日常生活中的场景。可以包含简单的顺序描述，"
        "比如先做什么再做什么。避免过于复杂的词汇。"
    ),
    "secondary_high": (
        "使用日常生活场景和简单顺序任务。"
        "可以涉及时间安排和简单归纳。"
    ),
    "college": (
        "可以包含稍复杂的复述、归纳和计划类问题。"
        "适当使用书面表达词汇。"
    ),
    "university": (
        "可以包含较为复杂的复述、归纳和计划类问题。"
        "可以使用较丰富的词汇和表达方式。"
    ),
}

# Opening messages by education level
OPENING_MESSAGES = {
    "basic": "您好，我是小忆。咱们随便聊聊天，不用紧张。最近吃饭还好吗？",
    "secondary_low": "您好，我是小忆。咱们就像平常聊天一样，不用紧张。最近吃饭还顺口吗？平时都吃些什么？",
    "secondary_high": "您好，我是小忆。咱们就像平常聊天一样，不用紧张。最近吃饭还顺口吗？平时早中晚大概会吃些什么？",
    "college": "您好，我是小忆。这是一个轻松的日常对话，您就像平时聊天一样回答就好。最近饮食和作息怎么样？",
    "university": "您好，我是小忆。这是一个轻松的日常对话，请您像平时聊天一样自然回答就好。最近饮食起居怎么样？",
}
