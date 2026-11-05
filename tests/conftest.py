"""公共夹具：把 session/todo/trace 落盘路径指到临时目录，LLM 换成剧本回放的 FakeLLM。"""
import pytest

from fake_llm import FakeLLM

from agent import llm, session as session_mod, tools, trace


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(session_mod, "SESSIONS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(tools, "TODO_PATH", tmp_path / ".todo.json")
    monkeypatch.setattr(trace, "LOG_PATH", tmp_path / "logs" / "trace.jsonl")
    return tmp_path


@pytest.fixture
def fake(env, monkeypatch):
    def make(*script):
        f = FakeLLM(*script)
        monkeypatch.setattr(llm, "chat", f.chat)
        return f
    return make
