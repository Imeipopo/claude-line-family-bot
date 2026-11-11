"""第一篇的檢查點：還沒接 Claude，只把收到的文字原樣回傳。能回就代表 LINE → 你的電腦這條路通了。

執行：python steps/ch1_echo.py
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import ApiClient, Configuration, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
parser = WebhookParser(os.environ["LINE_CHANNEL_SECRET"])
line_config = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
app = FastAPI()


@app.post("/webhook")
async def webhook(request: Request, x_line_signature: str = Header(None)) -> dict:
    body = (await request.body()).decode("utf-8")
    try:
        events = parser.parse(body, x_line_signature or "")
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="invalid signature")
    with ApiClient(line_config) as api_client:
        api = MessagingApi(api_client)
        for event in events:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                source = event.source
                # 順便印出 id：第二篇以後要填進 .env 的 BOT_USER_ID／OWNER_USER_ID 就從這裡抄
                print(f"type={source.type} user_id={source.user_id} "
                      f"group_id={getattr(source, 'group_id', None)} text={event.message.text}", flush=True)
                if os.environ.get("DRY_RUN") == "1":
                    print(f"[DRY_RUN reply] 你說：{event.message.text}", flush=True)
                    continue
                api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"你說：{event.message.text}")],
                ))
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8001")))
