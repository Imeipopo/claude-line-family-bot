"""長期記憶：Claude 自己能讀寫的 knowledge_auto.md，加上每晚整理一次當天對話。"""
from config import AUTO_KNOWLEDGE_FILE, BOT_NAME

MAX_BYTES = 256 * 1024

TOOLS = [
    {
        "name": "recall_auto_knowledge",
        "description": "讀取你自己累積的長期記憶。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "update_auto_knowledge",
        "description": (
            "整份覆寫長期記憶。呼叫前一定要先 recall_auto_knowledge，"
            "把舊內容保留並加上新事實後整份寫回，不能讓舊事實消失。"
            "只記值得長期記住的家裡事實，日常瑣事不要寫。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
    },
]


def recall() -> str:
    if AUTO_KNOWLEDGE_FILE.exists() and AUTO_KNOWLEDGE_FILE.read_text().strip():
        return AUTO_KNOWLEDGE_FILE.read_text()
    return "（目前還沒有長期記憶）"


def write(content: str) -> str:
    data = content.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError("長期記憶太長了")
    AUTO_KNOWLEDGE_FILE.write_bytes(data)
    return f"已更新長期記憶（{len(data)} bytes）"


def run(name: str, args: dict, ctx: dict) -> str:
    if name == "recall_auto_knowledge":
        return recall()
    if name == "update_auto_knowledge":
        return write(args["content"])
    raise KeyError(name)


def build_review_prompt(history: list) -> str:
    convo = "\n".join(f"{h['speaker']}：{h['text']}" for h in history)
    return (
        f"你是家庭群組助理「{BOT_NAME}」的記憶整理員。以下是「目前已記住的家裡事實」和「今天的群組對話」。\n"
        "請找出對話裡值得長期記住的新事實：誰住哪、生日、健康狀況、過敏、職業變動、長期偏好、重要的長期計畫。\n"
        "規則：\n"
        "- 日常瑣事、情緒抒發、單次事件、約時間都不要記。\n"
        "- 有新事實時，輸出完整更新後的清單：第一行固定是「# 自動累積的家裡知識」，下面每條用「- 」開頭，舊的每一條都要保留。\n"
        "- 沒有值得記的新事實，只輸出 NONE。\n\n"
        f"【目前已記住】\n{recall()}\n\n【今天的對話】\n{convo}"
    )


def clean_review_output(text: str) -> str | None:
    """模型偶爾會多講開場白，這裡只留標題與「- 」條列；沒有任何事實就回 None。"""
    text = text.strip()
    if not text or text == "NONE":
        return None
    lines, started = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("# 自動累積"):
            started, lines = True, ["# 自動累積的家裡知識", ""]
        elif started and line.startswith("- "):
            lines.append(line)
    if len(lines) <= 2:
        return None
    return "\n".join(lines) + "\n"
