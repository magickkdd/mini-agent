"""公共夹具：落盘路径指向临时目录；按是否设置 OPENAI_API_KEY 自动切换模型驱动。

- 未设置 key：driver(*script) 返回 FakeLLM 剧本回放（确定性、零 token）；
- 设置了 key：返回真实 llm.chat，剧本参数被忽略（同一套用例直接跑真模型）。
pytest_report_header 在报告头标明当前模式。
"""
import os

import pytest

from fake_llm import FakeLLM

from agent import llm, session as session_mod, tools, trace

REAL_API = bool(os.environ.get("OPENAI_API_KEY"))


def pytest_report_header(config):
    if REAL_API:
        return ("已检测到 OPENAI_API_KEY：以下用例使用真模型执行"
                "（剧本参数仅作为预期行为说明，被忽略）")
    return ("[提示] 未检测到 OPENAI_API_KEY：模型回复由 FakeLLM 按剧本回放；"
            "设置该环境变量后同一套用例将自动改用真模型执行")


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(tools, "TODO_PATH", tmp_path / ".todo.json")
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "logs" / "trace.jsonl")
    return tmp_path


@pytest.fixture
def driver(env, monkeypatch):
    if REAL_API:
        return lambda *script: llm.chat
    def make(*script):
        f = FakeLLM(*script)
        monkeypatch.setattr(llm, "chat", f.chat)
        return f.chat
    return make
