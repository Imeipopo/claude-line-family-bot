# claude-line-family-bot

把 Claude 放進 LINE 家庭群組的小助理「小欣」。被 @ 才回話、會上網查資料、能記事、會提醒、看得懂照片，每晚自己整理家裡的長期記憶。

這份程式是從我家實際在跑的家庭群組機器人整理出來的精簡版（去掉家人資料與個人設定）。完整的從零教學在我的部落格，共五篇：

1. LINE 官方帳號與 webhook：讓訊息送得到你的電腦
2. 接上模型：以 Claude 為例，以及模型怎麼選
3. 人設、@ 才回、群組前後文、上網查資料
4. 給它工具：提醒、備忘錄、長期記憶、看照片
5. 常駐上線：開機自動跑、固定網址、費用控管

## 需要準備

- 一台會一直開著的電腦（教學用 Apple Silicon Mac；Linux 也行，常駐方式要自己換）
- Python 3.11 以上
- LINE 官方帳號＋Messaging API channel（免費方案即可）
- Claude Console 的 API 金鑰（用量計費；我家估計一個月 3～4 美元）
- Cloudflare 帳號（Tunnel 免費），用來讓 LINE 連到你的電腦

## 快速開始

```bash
git clone https://github.com/Imeipopo/claude-line-family-bot.git
cd claude-line-family-bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env              # 填入 LINE 與 Claude 的金鑰
cp knowledge.example.md knowledge.md   # 選填：家裡的固定資訊
venv/bin/python main.py
```

### 沒有 LINE 也能先測

在 `.env` 設 `DRY_RUN=1`，機器人不會真的呼叫 LINE，而是把要回的話印在終端機。另開一個終端機：

```bash
venv/bin/python scripts/fake_line_event.py "台中明天會下雨嗎"
venv/bin/python scripts/fake_line_event.py --group "@小欣 幫我記一下：週日要回診"
```

`fake_line_event.py` 會用你的 Channel secret 算出和 LINE 一樣的簽章，所以走的是完整的 webhook 流程，Claude 也是真的被呼叫。

### 單元測試

```bash
venv/bin/python -m unittest discover -s tests
```

## 檔案

| 檔案 | 做什麼 |
| --- | --- |
| `main.py` | webhook 入口：驗簽章、判斷要不要回、交給 Claude、回到群組 |
| `claude_client.py` | 組系統提示、帶工具、跑工具迴圈 |
| `mention.py` | 判斷有沒有被 @ 或被回覆 |
| `line_api.py` | 回覆與主動推播（含 DRY_RUN） |
| `tools_notes.py` | 備忘錄工具（擋路徑穿越） |
| `tools_reminders.py` | 提醒工具（APScheduler，重開後還在） |
| `tools_memory.py` | 長期記憶與每晚整理 |
| `usage.py` | 記錄 token 與搜尋次數、算花費、超標警報 |
| `persona.md` | 小欣的人設，想換名字或個性就改這裡 |
| `steps/ch1_echo.py` | 第一篇的檢查點：只會鸚鵡學話的最小版本 |
| `ops/` | macOS 開機自動啟動與 Cloudflare Tunnel 設定範例 |

執行時產生的資料（對話紀錄、提醒、記事、記憶、用量）都在 `data/`，已列在 `.gitignore`，不會被 commit。

## 隱私提醒

機器人看得到群組裡所有文字（用來理解前後文，以及每晚整理記憶），照片則是有人 @ 它時才會下載。放進家庭群組前，請先讓家人知道它會看、會記什麼。

## 授權

MIT
