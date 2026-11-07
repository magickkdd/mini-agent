"""公共夹具：落盘路径指向临时目录；按是否设置 OPENAI_API_KEY 自动切换测试模式。

- 未设置 key：LLM 用例使用 FakeLLM 剧本回放（确定性逻辑测试），报告头给出提醒；
- 设置了 key：FakeLLM 用例自动跳过，tests/test_live.py 的真模型用例接管。
"""
import os

import pytest

from fake_llm import FakeLLM

from agent import llm, session as session_mod, tools, trace

REAL_API = bool(os.environ.get("OPENAI_API_KEY"))


def pytest_report_header(config):
    if REAL_API:
        return ("已检测到 OPENAI_API_KEY：test_agent.py 的 FakeLLM 用例自动跳过，"
                "运行 tests/test_live.py 真模型行为测试")
    return ("[提示] 未检测到 OPENAI_API_KEY：LLM 用例使用 FakeLLM 剧本回放；"
            "设置该环境变量后将自动改跑真模型用例 tests/test_live.py")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(tools, "TODO_PATH", tmp_path / ".todo.json")
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "logs" / "trace.jsonl")
    return tmp_path


@pytest.fixture
def fake(env, monkeypatch):
    if REAL_API:
        pytest.skip("已设置 OPENAI_API_KEY：跳过 FakeLLM 用例，改由 tests/test_live.py 跑真模型")
    def make(*script):
        f = FakeLLM(*script)
        monkeypatch.setattr(llm, "chat", f.chat)
        return f
    return make
