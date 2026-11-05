"""执行日志：LLM 调用、工具执行、压缩事件全部追加写入 logs/trace.jsonl。"""
import json
import time
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "trace.jsonl"


def log(sid, event, **data):
    entry = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "sid": sid, "event": event, **data}
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
