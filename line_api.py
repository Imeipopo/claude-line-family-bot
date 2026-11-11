from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)

from config import CHANNEL_ACCESS_TOKEN, DRY_RUN, REPLY_LIMIT

line_config = Configuration(access_token=CHANNEL_ACCESS_TOKEN)


def _clip(text: str) -> str:
    if len(text) > REPLY_LIMIT:
        return text[:REPLY_LIMIT] + "\n\n...（已截斷）"
    return text


def reply_text(api: MessagingApi, reply_token: str, text: str) -> list[str]:
    """回覆被 @ 的那則訊息，回傳 LINE 給的訊息 id（之後用來認出「有人回覆我」）。"""
    text = _clip(text)
    if DRY_RUN:
        print(f"[DRY_RUN reply] {text}", flush=True)
        return [f"dry-{reply_token}"]
    response = api.reply_message(
        ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)])
    )
    return [m.id for m in (getattr(response, "sent_messages", None) or []) if getattr(m, "id", None)]


def push_text(target_id: str, text: str) -> list[str]:
    """主動傳訊息（提醒、警報用）。push 會算進 LINE 每月免費則數。"""
    text = _clip(text)
    if DRY_RUN:
        print(f"[DRY_RUN push → {target_id}] {text}", flush=True)
        return []
    with ApiClient(line_config) as api_client:
        response = MessagingApi(api_client).push_message(
            PushMessageRequest(to=target_id, messages=[TextMessage(text=text)])
        )
    return [m.id for m in (getattr(response, "sent_messages", None) or []) if getattr(m, "id", None)]
