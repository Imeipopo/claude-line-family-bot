def session_key(source) -> str:
    """同一個群組／聊天室／私訊共用一份對話紀錄。"""
    if source.type == "group":
        return f"group:{source.group_id}"
    if source.type == "room":
        return f"room:{source.room_id}"
    return f"user:{source.user_id}"


def is_mentioned(message, source_type: str, bot_user_id: str, bot_msg_ids: list) -> bool:
    """私訊一律回；群組裡只有被 @，或有人「回覆」機器人自己的訊息時才回。"""
    if source_type == "user":
        return True
    mention = getattr(message, "mention", None)
    if mention and bot_user_id:
        # 有人 @All 時 mentionee 沒有 user_id，要用 getattr 才不會整個崩潰
        if any(getattr(m, "user_id", None) == bot_user_id for m in mention.mentionees):
            return True
    quoted_id = getattr(message, "quoted_message_id", None)
    return bool(quoted_id and quoted_id in bot_msg_ids)


def strip_mention(text: str) -> str:
    """把開頭的「@小欣 」拿掉，只留真正的問題。"""
    parts = text.split(maxsplit=1)
    if parts and parts[0].startswith("@"):
        return parts[1] if len(parts) > 1 else ""
    return text
