"""不用手機、不用 LINE，自己做一個「LINE 送來的訊息」打到本機 webhook，搭配 DRY_RUN=1 測試。

用法：
  python scripts/fake_line_event.py "今天台中會下雨嗎"            # 私訊
  python scripts/fake_line_event.py --group "@小欣 今天台中會下雨嗎"  # 群組裡 @ 機器人
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

ap = argparse.ArgumentParser()
ap.add_argument("text")
ap.add_argument("--group", action="store_true", help="模擬群組訊息；文字以 @ 開頭時會標成 @ 機器人")
ap.add_argument("--user", default=os.environ.get("OWNER_USER_ID") or "Utestuser000000000000000000000000")
args = ap.parse_args()

source = {"type": "user", "userId": args.user}
message = {"type": "text", "id": str(int(time.time() * 1000)), "text": args.text, "quoteToken": "q"}
if args.group:
    source = {"type": "group", "groupId": "Ctestgroup0000000000000000000000", "userId": args.user}
if args.group and args.text.startswith("@"):
    name = args.text.split()[0]
    message["mention"] = {"mentionees": [{
        "index": 0, "length": len(name), "type": "user",
        "userId": os.environ.get("BOT_USER_ID", ""),
    }]}

body = json.dumps({
    "destination": "Utestbot",
    "events": [{
        "type": "message", "mode": "active", "timestamp": int(time.time() * 1000),
        "webhookEventId": "test", "deliveryContext": {"isRedelivery": False},
        "replyToken": "test-reply-token", "source": source, "message": message,
    }],
}).encode()
# LINE 的簽章：用 Channel secret 對整個 body 做 HMAC-SHA256，再 base64
signature = base64.b64encode(
    hmac.new(os.environ["LINE_CHANNEL_SECRET"].encode(), body, hashlib.sha256).digest()
).decode()
req = urllib.request.Request(
    f"http://127.0.0.1:{os.environ.get('PORT', '8001')}/webhook",
    data=body, headers={"Content-Type": "application/json", "X-Line-Signature": signature},
)
with urllib.request.urlopen(req, timeout=300) as resp:
    print(resp.status, resp.read().decode())
