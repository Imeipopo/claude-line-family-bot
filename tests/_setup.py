import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["BOT_DATA_DIR"] = tempfile.mkdtemp(prefix="linebot-test-")
for name in ("LINE_CHANNEL_SECRET", "LINE_CHANNEL_ACCESS_TOKEN"):
    os.environ.setdefault(name, "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ["DRY_RUN"] = "1"
