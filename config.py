import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).parent
load_dotenv(PROJECT_DIR / ".env")

CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
BOT_USER_ID = os.environ.get("BOT_USER_ID", "")
OWNER_USER_ID = os.environ.get("OWNER_USER_ID", "")
ALLOWED_USERS = [u for u in os.environ.get("ALLOWED_USERS", "").split(",") if u]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")
BOT_NAME = os.environ.get("BOT_NAME", "小欣")
PORT = int(os.environ.get("PORT", "8001"))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

TZ = ZoneInfo("Asia/Taipei")

DATA_DIR = Path(os.environ.get("BOT_DATA_DIR", PROJECT_DIR / "data"))
DATA_DIR.mkdir(exist_ok=True)
GROUP_STATE_FILE = DATA_DIR / "group_state.json"
SCHEDULES_FILE = DATA_DIR / "schedules.json"
USAGE_LOG = DATA_DIR / "usage.jsonl"
COST_STATE_FILE = DATA_DIR / "cost_alert_state.json"
AUTO_KNOWLEDGE_FILE = DATA_DIR / "knowledge_auto.md"
NOTES_DIR = DATA_DIR / "notes"
NOTES_DIR.mkdir(exist_ok=True)

PERSONA_FILE = PROJECT_DIR / "persona.md"
KNOWLEDGE_FILE = PROJECT_DIR / "knowledge.md"

CONTEXT_LIMIT = 30       # 回話時帶給 Claude 的群組近期對話句數
BOT_MSG_LIMIT = 100      # 記住自己最近發過的訊息 id，用來判斷「有人回覆我」
DAY_BUFFER_MAX = 500     # 每晚整理記憶用的當天對話上限
TOOL_LOOP_MAX = 8        # 一則訊息最多讓 Claude 連續用幾次工具
REPLY_LIMIT = 4900       # LINE 單則文字上限 5000 字，留一點空間


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
