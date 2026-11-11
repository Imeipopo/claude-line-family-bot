"""LINE webhook 入口：收訊息 → 判斷要不要回 → 交給 Claude → 回到群組。"""
from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import ApiClient, MessagingApi, MessagingApiBlob
from linebot.v3.webhooks import ImageMessageContent, MessageEvent, TextMessageContent

import tools_memory
import usage
from claude_client import ask_once, call_claude
from config import (
    ALLOWED_USERS, BOT_MSG_LIMIT, BOT_NAME, BOT_USER_ID, CHANNEL_SECRET, CONTEXT_LIMIT,
    DAY_BUFFER_MAX, DRY_RUN, GROUP_STATE_FILE, OWNER_USER_ID, PORT, TZ, load_json, save_json,
)
from line_api import line_config, reply_text
from mention import is_mentioned, session_key, strip_mention
from tools_reminders import load_saved_reminders, scheduler

parser = WebhookParser(CHANNEL_SECRET)

RESET_WORDS = ("/new", "重新開始", "清除")
IMAGE_WINDOW_SECONDS = 180


def now_text() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M %A")


def build_prompt(speaker: str, text: str, history: list) -> str:
    # 「目前時間」放在使用者訊息裡而不是系統提示，系統提示才能一直吃快取
    parts = [f"---目前時間---\n{now_text()}（台北）"]
    if history:
        parts.append("---群組最近對話---\n" + "\n".join(f"{h['speaker']}：{h['text']}" for h in history))
    parts.append(f"現在 {speaker} @ 你說：{text}")
    return "\n\n".join(parts)


def display_name(api: MessagingApi, source, names: dict) -> str:
    user_id = source.user_id
    if user_id in names:
        return names[user_id]
    name = user_id[:8]
    if not DRY_RUN:
        try:
            if source.type == "group":
                name = api.get_group_member_profile(source.group_id, user_id).display_name
            elif source.type == "room":
                name = api.get_room_member_profile(source.room_id, user_id).display_name
            else:
                name = api.get_profile(user_id).display_name
        except Exception as e:
            print(f"[LINE] 讀不到暱稱 {user_id[:8]}：{e}", flush=True)
    names[user_id] = name
    return name


def remember_sent(state: dict, key: str, sent_ids: list) -> None:
    ids = state["bot_msg_ids"].setdefault(key, [])
    ids.extend(sent_ids)
    del ids[:-BOT_MSG_LIMIT]


def target_of(source) -> str:
    return getattr(source, "group_id", None) or getattr(source, "room_id", None) or source.user_id


def run_daily_memory_review() -> None:
    state = load_json(GROUP_STATE_FILE, {})
    for key, history in state.get("day_buffer", {}).items():
        if history:
            updated = tools_memory.clean_review_output(ask_once(tools_memory.build_review_prompt(history)))
            if updated:
                tools_memory.write(updated)
                print(f"[MEMORY] {key} 有新事實，已更新", flush=True)
    state["day_buffer"] = {}
    save_json(GROUP_STATE_FILE, state)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 伺服器啟動時：排回存檔的提醒，加上「每 30 分鐘查花費」「每晚 11 點整理記憶」兩個固定工作
    load_saved_reminders()
    scheduler.add_job(usage.check_cost_alerts, CronTrigger.from_crontab("*/30 * * * *", timezone=TZ),
                      id="__cost_check", replace_existing=True)
    scheduler.add_job(run_daily_memory_review, CronTrigger.from_crontab("0 23 * * *", timezone=TZ),
                      id="__memory_review", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(request: Request, x_line_signature: str = Header(None)) -> dict:
    body = (await request.body()).decode("utf-8")
    if not x_line_signature:
        raise HTTPException(status_code=400, detail="missing signature")
    try:
        # 用 Channel secret 驗簽章：確定這個請求真的是 LINE 送來的，不是別人亂打
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="invalid signature")

    state = load_json(GROUP_STATE_FILE, {})
    for field in ("contexts", "names", "bot_msg_ids", "day_buffer", "last_image"):
        state.setdefault(field, {})

    with ApiClient(line_config) as api_client:
        api = MessagingApi(api_client)
        blob_api = MessagingApiBlob(api_client)
        for event in events:
            if isinstance(event, MessageEvent):
                handle_message(event, state, api, blob_api)
    save_json(GROUP_STATE_FILE, state)
    return {"status": "ok"}


def handle_message(event: MessageEvent, state: dict, api: MessagingApi, blob_api: MessagingApiBlob) -> None:
    source = event.source
    key = session_key(source)
    in_group = source.type in ("group", "room")

    if source.type == "user" and OWNER_USER_ID and source.user_id != OWNER_USER_ID:
        return  # 私訊只回主人，避免陌生人加好友就能花你的 API 費
    if in_group and ALLOWED_USERS and source.user_id not in ALLOWED_USERS:
        return

    if isinstance(event.message, ImageMessageContent):
        if in_group:
            # 群組照片先只記 id，等有人 @ 機器人時才真的下載來看
            state["last_image"][key] = {"id": event.message.id, "ts": datetime.now(TZ).timestamp()}
            return
        image = bytes(blob_api.get_message_content(event.message.id))
        speaker = display_name(api, source, state["names"])
        prompt = f"---目前時間---\n{now_text()}（台北）\n\n{speaker} 傳了一張照片給你，請給真誠具體的回應。"
        answer = call_claude(prompt, target_id=target_of(source), images=[image])
        remember_sent(state, key, reply_text(api, event.reply_token, answer))
        return

    if not isinstance(event.message, TextMessageContent):
        return

    speaker = display_name(api, source, state["names"])
    raw_text = event.message.text
    if in_group:
        history = state["contexts"].setdefault(key, [])
        history.append({"speaker": speaker, "text": raw_text})
        del history[:-CONTEXT_LIMIT]
        day = state["day_buffer"].setdefault(key, [])
        day.append({"speaker": speaker, "text": raw_text})
        del day[:-DAY_BUFFER_MAX]

    if not is_mentioned(event.message, source.type, BOT_USER_ID, state["bot_msg_ids"].get(key, [])):
        return
    text = strip_mention(raw_text).strip()
    if not text:
        return

    if text in RESET_WORDS:
        state["contexts"][key] = []
        remember_sent(state, key, reply_text(api, event.reply_token, "好，前面的對話我先放下，重新開始。"))
        return

    history = state["contexts"].get(key, [])[:-1]  # 最後一句就是現在這句，不要重複
    images = None
    last = state["last_image"].pop(key, None)  # 用過就清掉，避免舊照片被之後的 @ 誤帶
    if last and datetime.now(TZ).timestamp() - last["ts"] < IMAGE_WINDOW_SECONDS:
        try:
            images = [bytes(blob_api.get_message_content(last["id"]))]
        except Exception as e:
            print(f"[LINE] 照片下載失敗：{e}", flush=True)

    answer = call_claude(build_prompt(speaker, text, history), target_id=target_of(source), images=images)
    if in_group:
        state["contexts"][key].append({"speaker": BOT_NAME, "text": answer})
    remember_sent(state, key, reply_text(api, event.reply_token, answer))


if __name__ == "__main__":
    import uvicorn

    # 只聽本機 127.0.0.1：外面只能透過 Cloudflare Tunnel 進來，區網的人也打不到
    uvicorn.run(app, host="127.0.0.1", port=PORT)
