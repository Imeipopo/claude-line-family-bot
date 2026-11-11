"""提醒工具：Claude 呼叫 add_reminder 時，真的用 APScheduler 排一個工作，並存檔讓重開後還在。"""
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from config import SCHEDULES_FILE, TZ, load_json, save_json
from line_api import push_text

scheduler = BackgroundScheduler(timezone=TZ)

TOOLS = [
    {
        "name": "add_reminder",
        "description": (
            "建立一次性提醒。label 是簡短的唯一名稱（例如「週六看牙醫」）。"
            "when 是台北時間的 ISO 字串，例如 2026-12-06T09:00:00。"
            "context 用一句話描述要提醒什麼，時間到時你會依此寫提醒訊息。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "when": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["label", "when", "context"],
        },
    },
    {
        "name": "add_recurring",
        "description": (
            "建立重複提醒，cron 是標準 5 欄（分 時 日 月 星期），例如「0 8 * * 1」＝每週一早上 8 點。"
            "label 是唯一名稱，context 描述要提醒什麼。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "cron": {"type": "string"},
                "context": {"type": "string"},
            },
            "required": ["label", "cron", "context"],
        },
    },
    {
        "name": "list_reminders",
        "description": "列出目前所有提醒。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "delete_reminder",
        "description": "依 label 取消提醒。",
        "input_schema": {
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
    },
]


def _reminder_prompt(context: str) -> str:
    return (
        f"提醒時間到了。要提醒的事情：{context}\n"
        "用你平常的口吻發一句簡短提醒（不超過 2 句），不要說「我來提醒你」，直接講內容。"
    )


def fire(label: str, context: str, target_id: str, once: bool) -> None:
    # 放在函式裡 import：claude_client 也會 import 這個檔案，寫在最上面會互相卡住
    from claude_client import call_claude

    print(f"[REMINDER] {label}", flush=True)
    try:
        push_text(target_id, call_claude(_reminder_prompt(context), target_id=target_id))
    except Exception as e:
        print(f"[REMINDER] {label} failed: {e}", flush=True)
    if once:
        save_json(SCHEDULES_FILE, [s for s in load_json(SCHEDULES_FILE, []) if s["label"] != label])


def _schedule(item: dict) -> None:
    if item["type"] == "once":
        trigger = DateTrigger(run_date=datetime.fromisoformat(item["when"]))
    else:
        trigger = CronTrigger.from_crontab(item["cron"], timezone=TZ)
    scheduler.add_job(
        fire,
        trigger=trigger,
        args=[item["label"], item["context"], item["target_id"], item["type"] == "once"],
        id=item["label"],
        replace_existing=True,
    )


def _save(item: dict) -> None:
    items = [s for s in load_json(SCHEDULES_FILE, []) if s["label"] != item["label"]]
    save_json(SCHEDULES_FILE, items + [item])


def load_saved_reminders() -> None:
    """啟動時把存檔裡的提醒排回去；已經過期的單次提醒直接丟掉。"""
    keep = []
    for item in load_json(SCHEDULES_FILE, []):
        if item["type"] == "once" and datetime.fromisoformat(item["when"]) <= datetime.now(TZ):
            continue
        _schedule(item)
        keep.append(item)
    save_json(SCHEDULES_FILE, keep)


def run(name: str, args: dict, ctx: dict) -> str:
    target_id = ctx.get("target_id")
    if name in ("add_reminder", "add_recurring") and not target_id:
        raise ValueError("不知道要提醒到哪個聊天室")
    if name == "add_reminder":
        when = datetime.fromisoformat(args["when"])
        if when.tzinfo is None:
            when = when.replace(tzinfo=TZ)
        if when <= datetime.now(TZ):
            raise ValueError(f"{args['when']} 已經過了")
        item = {"label": args["label"], "type": "once", "when": when.isoformat(),
                "context": args["context"], "target_id": target_id}
        _schedule(item)
        _save(item)
        return f"已建立提醒「{item['label']}」：{when:%Y-%m-%d %H:%M}"
    if name == "add_recurring":
        CronTrigger.from_crontab(args["cron"], timezone=TZ)  # 格式錯會在這裡就報錯，不會存進去
        item = {"label": args["label"], "type": "cron", "cron": args["cron"],
                "context": args["context"], "target_id": target_id}
        _schedule(item)
        _save(item)
        return f"已建立重複提醒「{item['label']}」（{item['cron']}）"
    if name == "list_reminders":
        items = load_json(SCHEDULES_FILE, [])
        return "\n".join(
            f"{s['label']}：{s.get('when') or s.get('cron')} → {s['context']}" for s in items
        ) or "（目前沒有提醒）"
    if name == "delete_reminder":
        items = load_json(SCHEDULES_FILE, [])
        remaining = [s for s in items if s["label"] != args["label"]]
        if len(remaining) == len(items):
            raise ValueError(f"找不到「{args['label']}」")
        save_json(SCHEDULES_FILE, remaining)
        if scheduler.get_job(args["label"]):
            scheduler.remove_job(args["label"])
        return f"已取消「{args['label']}」"
    raise KeyError(name)
