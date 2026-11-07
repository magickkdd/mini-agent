"""公共夹具：落盘路径指向临时目录；未设置 OPENAI_API_KEY 时提醒并直接退出。"""
import os

import pytest

from agent import session as session_mod, tools, trace


def pytest_configure(config):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.exit("[提示] 未检测到 OPENAI_API_KEY，测试退出。\n"
                    "请先在环境变量中设置 OPENAI_API_KEY"
                    "（可选 OPENAI_BASE_URL / AGENT_MODEL），然后重跑本命令。",
                    returncode=0)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(tools, "TODO_PATH", tmp_path / ".todo.json")
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "logs" / "trace.jsonl")
    return tmp_path
