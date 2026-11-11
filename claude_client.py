"""跟 Claude 對話的核心：組系統提示、帶工具、跑「Claude 要用工具 → 我們執行 → 把結果還給它」的迴圈。"""
import base64

import anthropic

import tools_memory
import tools_notes
import tools_reminders
import usage
from config import KNOWLEDGE_FILE, MODEL, PERSONA_FILE, TOOL_LOOP_MAX

client = anthropic.Anthropic()  # 自動讀環境變數 ANTHROPIC_API_KEY

# Anthropic 幫忙執行的「伺服器工具」：我們不用寫程式，結果直接出現在回應裡
WEB_SEARCH = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}

# 我們自己寫的工具：工具名稱 → 負責執行的模組
TOOL_MODULES = {
    tool["name"]: module
    for module in (tools_notes, tools_reminders, tools_memory)
    for tool in module.TOOLS
}
TOOLS = [WEB_SEARCH, *tools_notes.TOOLS, *tools_reminders.TOOLS, *tools_memory.TOOLS]


def build_system() -> list[dict]:
    # 不常變的內容放前面並標 cache_control，下次呼叫可以吃快取，比較省錢
    system = [{"type": "text", "text": PERSONA_FILE.read_text(), "cache_control": {"type": "ephemeral"}}]
    if KNOWLEDGE_FILE.exists():
        system.append({"type": "text", "text": f"---家裡資訊---\n{KNOWLEDGE_FILE.read_text()}"})
    memory = tools_memory.recall()
    system.append({"type": "text", "text": f"---你自己累積的長期記憶---\n{memory}"})
    return system


def text_of(content) -> str:
    # 有查網路時，同一段話會因為引用來源被切成好幾個 text 區塊，要直接接起來，不能用換行接
    return "".join(b.text for b in content if b.type == "text" and b.text).strip()


def ask_once(prompt: str) -> str:
    """不帶工具、不帶人設的單次問答，給每晚整理記憶用。"""
    response = client.messages.create(
        model=MODEL, max_tokens=4096, messages=[{"role": "user", "content": prompt}]
    )
    usage.log_usage(MODEL, response.usage)
    return text_of(response.content)


def call_claude(prompt: str, *, target_id: str = "", images: list[bytes] | None = None) -> str:
    content: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                     "data": base64.b64encode(img).decode("ascii")}}
        for img in images or []
    ]
    content.append({"type": "text", "text": prompt})
    messages = [{"role": "user", "content": content}]
    system = build_system()

    for _ in range(TOOL_LOOP_MAX):
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=4096, system=system, tools=TOOLS, messages=messages
            )
        except anthropic.APIError as e:
            print(f"[CLAUDE] {type(e).__name__}: {e}", flush=True)
            return "我這邊連不上，晚點再問我一次好嗎？"
        usage.log_usage(MODEL, response.usage)

        if response.stop_reason == "refusal":
            return "這個我沒辦法回答。"
        if response.stop_reason == "pause_turn":
            # 搜尋這類伺服器工具跑太久會先暫停，把目前內容原封不動送回去，它就會接著做
            messages.append({"role": "assistant", "content": response.content})
            continue
        if response.stop_reason != "tool_use":
            return text_of(response.content) or "（沒有回應）"

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                output = TOOL_MODULES[block.name].run(block.name, block.input, {"target_id": target_id})
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
            except Exception as e:
                # 工具出錯不要讓整支程式掛掉，把錯誤告訴 Claude，它會自己換方法或跟家人說明
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": str(e), "is_error": True})
        messages.append({"role": "user", "content": results})

    return "（這題我轉太多圈了，先停在這裡）"
