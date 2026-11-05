"""多 session 隔离与持久化（Claude Code 转写文件模式极简版）。

每个 session 一个 JSONL 文件，消息逐条追加；重启后按 session_id 重放恢复。
不同 session 的 messages 完全隔离，互不影响。
"""
import json
from pathlib import Path

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"


class Session:
    def __init__(self, sid):
        self.sid = sid
        self.messages = []
        self.path = SESSIONS_DIR / f"{sid}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, msg):
        self.messages.append(msg)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def rewrite(self):
        """压缩后整体重写（正常对话只追加，不用到此方法）。"""
        with self.path.open("w", encoding="utf-8") as f:
            for m in self.messages:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")


class SessionManager:
    """dict[sid] -> Session；首次访问时从 JSONL 重放恢复历史。"""

    def __init__(self):
        self.sessions = {}

    def get(self, sid):
        if sid not in self.sessions:
            s = Session(sid)
            if s.path.exists():
                s.messages = [json.loads(line)
                              for line in s.path.read_text("utf-8").splitlines() if line.strip()]
            self.sessions[sid] = s
        return self.sessions[sid]
