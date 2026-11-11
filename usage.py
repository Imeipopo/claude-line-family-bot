"""記錄每次呼叫用了多少 token，算出花費，超過門檻就私訊主人。"""
import json
from datetime import datetime

from config import COST_STATE_FILE, OWNER_USER_ID, TZ, USAGE_LOG, load_json, save_json
from line_api import push_text

# 每百萬 token 的美元價格（input / output / 讀快取 / 寫快取），以 Claude 官網價目表為準
PRICING = {
    "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125),
    "claude-sonnet-5": (2.00, 10.00, 0.20, 2.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.10, 2.50),
    "claude-opus-5-5": (4.00, 20.00, 0.20, 5.00),
}
WEB_SEARCH_USD = 10.00 / 1000  # 每次搜尋另計
DAILY_LIMIT_USD = 1.0
MONTHLY_LIMIT_USD = 20.0


def log_usage(model: str, usage) -> None:
    server_tools = getattr(usage, "server_tool_use", None)
    entry = {
        "ts": datetime.now(TZ).isoformat(timespec="seconds"),
        "model": model,
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_write": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "web_search": getattr(server_tools, "web_search_requests", 0) or 0,
    }
    with USAGE_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def entry_cost(entry: dict) -> float:
    price_in, price_out, price_cr, price_cw = PRICING.get(entry["model"], PRICING["claude-sonnet-5"])
    tokens = (
        entry["input"] * price_in
        + entry["output"] * price_out
        + entry["cache_read"] * price_cr
        + entry["cache_write"] * price_cw
    ) / 1_000_000
    return tokens + entry.get("web_search", 0) * WEB_SEARCH_USD


def total_cost(prefix: str) -> float:
    """prefix 給「2026-11」算整個月，給「2026-11-11」算當天。"""
    if not USAGE_LOG.exists():
        return 0.0
    total = 0.0
    for line in USAGE_LOG.read_text().splitlines():
        entry = json.loads(line)
        if entry["ts"].startswith(prefix):
            total += entry_cost(entry)
    return total


def check_cost_alerts() -> None:
    if not OWNER_USER_ID:
        return
    now = datetime.now(TZ)
    today, month = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
    state = load_json(COST_STATE_FILE, {})
    alerts = []
    daily, monthly = total_cost(today), total_cost(month)
    if daily > DAILY_LIMIT_USD and state.get("daily") != today:
        alerts.append(f"今天已花 ${daily:.2f}（門檻 ${DAILY_LIMIT_USD}）")
        state["daily"] = today
    if monthly > MONTHLY_LIMIT_USD and state.get("monthly") != month:
        alerts.append(f"這個月已花 ${monthly:.2f}（門檻 ${MONTHLY_LIMIT_USD}）")
        state["monthly"] = month
    if alerts:
        push_text(OWNER_USER_ID, "[花費警報]\n" + "\n".join(alerts))
        save_json(COST_STATE_FILE, state)
