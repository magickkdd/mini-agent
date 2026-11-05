"""REPL 客户端：--session 指定会话 ID，不同 ID 即不同窗口（开两个终端即两个窗口）。"""
import argparse

from agent import llm
from agent.runtime import run
from agent.session import SessionManager


def main():
    ap = argparse.ArgumentParser(description="MiniAgent —— 最小可用 Agent")
    ap.add_argument("--session", default="default", help="会话 ID，不同 ID 即不同窗口")
    args = ap.parse_args()
    mgr = SessionManager()
    s = mgr.get(args.session)
    print(f"MiniAgent | 会话: {args.session} | 历史 {len(s.messages)} 条 | 输入 exit 退出")
    while True:
        try:
            text = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):  # Ctrl-D / Ctrl-C 正常离开 REPL
            break
        if not text or text in ("exit", "quit"):
            if text:
                break
            continue
        print(f"\nAgent> {run(s, text)}")
        print(f"[tokens 累计] input={llm.usage['input']} output={llm.usage['output']}")


if __name__ == "__main__":
    main()
