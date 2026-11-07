"""真模型行为测试：仅在设置了 OPENAI_API_KEY 时运行（否则整文件跳过）。

断言放宽到"结果级"（回答非空 / 关键词命中 / 落盘生效），不锁定措辞与路径，
因此对任何 OpenAI-compatible 模型都稳定。runtime 的 LLM 失败兜底会返回
"LLM 调用失败: ..." 字符串，这里统一视为失败而非有效回答。
"""
import json
import os

import pytest

from agent.runtime import run
from agent.session import SessionManager

REAL_API = bool(os.environ.get("OPENAI_API_KEY"))

pytestmark = pytest.mark.skipif(
    not REAL_API, reason="未设置 OPENAI_API_KEY：真模型用例跳过（FakeLLM 逻辑测试照常运行）")


def real_answer(session, text):
    a = run(session, text)
    assert a and a.strip() and "LLM 调用失败" not in a, f"真模型调用未成功: {a}"
    return a


def test_live_chat(env):
    real_answer(SessionManager().get("live-chat"), "用一句话介绍你自己")


def test_live_calculator(env):
    a = real_answer(SessionManager().get("live-calc"), "请用 calculator 工具计算 (12+8)*3")
    assert "60" in a


def test_live_todo(env):
    real_answer(SessionManager().get("live-todo"), "请用 todo 工具记一个待办：买牛奶")
    assert "买牛奶" in (env / ".todo.json").read_text("utf-8")


def test_live_followup(env):
    s = SessionManager().get("live-follow")
    real_answer(s, "请用 todo 工具记一个待办：写周报")
    a = real_answer(s, "我刚才记了什么待办？")
    assert "写周报" in a


def test_live_isolation(env):
    mgr = SessionManager()
    real_answer(mgr.get("w1"), "用一句话介绍 Python")
    real_answer(mgr.get("w2"), "用一句话介绍围棋")
    w1 = json.dumps(mgr.get("w1").messages, ensure_ascii=False)
    w2 = json.dumps(mgr.get("w2").messages, ensure_ascii=False)
    assert "围棋" not in w1 and "介绍围棋" not in w1
    assert "介绍 Python" not in w2
    assert mgr.get("w1").path.exists() and mgr.get("w2").path.exists()
