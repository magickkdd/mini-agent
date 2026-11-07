"""公共夹具：落盘路径指向临时目录；按是否设置 OPENAI_API_KEY 决定模型相关用例去留。

- 设置了 key：全部用例直接跑真模型；
- 未设置 key：模型相关用例（标记 @needs_llm）自动跳过，报告头提醒；工具级用例照常运行。
"""
import os

import pytest

from agent import session as session_mod, tools, trace

HAS_KEY = bool(os.environ.get("OPENAI_API_KEY"))

needs_llm = pytest.mark.skipif(not HAS_KEY, reason="未设置 OPENAI_API_KEY：模型相关用例跳过")


def pytest_report_header(config):
    if HAS_KEY:
        return "已检测到 OPENAI_API_KEY：全部用例使用真模型执行"
    return ("[提示] 未检测到 OPENAI_API_KEY：模型相关用例已跳过"
            "（设置环境变量后同一套用例将直接跑真模型）")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(tools, "TODO_PATH", tmp_path / ".todo.json")
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "logs" / "trace.jsonl")
    return tmp_path
