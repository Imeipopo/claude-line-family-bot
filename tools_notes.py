"""備忘錄工具：讓 Claude 在 data/notes 裡讀寫檔案，但絕對出不了這個資料夾。"""
from datetime import datetime
from pathlib import Path

from config import NOTES_DIR

NOTES_ROOT = NOTES_DIR.resolve()
ALLOWED_EXT = {".md", ".txt"}
MAX_BYTES = 1024 * 1024

TOOLS = [
    {
        "name": "list_notes",
        "description": "列出備忘錄資料夾裡所有檔案，附大小與最後修改時間。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_note",
        "description": "讀取一個備忘錄檔案。filename 例如 todo.md。",
        "input_schema": {
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
    },
    {
        "name": "write_note",
        "description": "寫入備忘錄檔案（整份覆蓋），只能用 .md 或 .txt。要追加內容請先 read_note 再整份寫回。",
        "input_schema": {
            "type": "object",
            "properties": {"filename": {"type": "string"}, "content": {"type": "string"}},
            "required": ["filename", "content"],
        },
    },
    {
        "name": "delete_note",
        "description": "刪除一個備忘錄檔案。",
        "input_schema": {
            "type": "object",
            "properties": {"filename": {"type": "string"}},
            "required": ["filename"],
        },
    },
]


def resolve_note_path(filename: str) -> Path:
    """擋掉 ../ 之類的路徑穿越：解析後的路徑一定要在 notes 資料夾裡。"""
    if not filename or "\x00" in filename:
        raise ValueError("檔名不能空白")
    candidate = (NOTES_ROOT / filename).resolve()
    if NOTES_ROOT not in candidate.parents:
        raise ValueError(f"{filename} 超出備忘錄資料夾範圍")
    if candidate.suffix.lower() not in ALLOWED_EXT:
        raise ValueError(f"只允許 {sorted(ALLOWED_EXT)} 副檔名")
    return candidate


def run(name: str, args: dict, ctx: dict) -> str:
    if name == "list_notes":
        items = [
            f"{p.name}\t{p.stat().st_size}B\t{datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M}"
            for p in sorted(NOTES_ROOT.iterdir())
            if p.is_file()
        ]
        return "\n".join(items) or "（資料夾是空的）"
    path = resolve_note_path(args["filename"])
    if name == "read_note":
        if not path.is_file():
            raise FileNotFoundError(f"{args['filename']} 不存在")
        return path.read_text()
    if name == "write_note":
        data = args["content"].encode("utf-8")
        if len(data) > MAX_BYTES:
            raise ValueError("內容太長")
        path.write_bytes(data)
        return f"已寫入 {path.name}（{len(data)} bytes）"
    if name == "delete_note":
        if not path.is_file():
            raise FileNotFoundError(f"{args['filename']} 不存在")
        path.unlink()
        return f"已刪除 {path.name}"
    raise KeyError(name)
