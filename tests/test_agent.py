"""功能验证矩阵：一套用例验证 Agent 的各个功能（需设置 OPENAI_API_KEY）。

模型回答**不设标准答案**——每个场景把实际问答打印出来（`pytest -s`）供人工判断
合理性；自动断言只锁定结构性事实（工具消息是否进历史、待办是否落盘、会话是否
互串、压缩后结构、轮次守卫），这些是本仓库代码的行为，与模型措辞无关。
"""
import json

import agent.runtime as runtime
from agent.context import maybe_compact
from agent.runtime import run
from agent.session import SessionManager
from agent.tools import TOOLS, run_tool, schemas


def good(a):
    """前置条件：功能真的执行了（非 runtime 的 LLM 失败兜底字符串）。"""
    assert a and a.strip() and "LLM 调用失败" not in a, f"功能未能执行: {a}"
    return a


def show(title, s, a):
    """打印场景的实际问答，供人工判断回答合理性。"""
    print(f"\n=== 场景：{title} ===")
    for m in s.messages[-3:]:
        print(f"[{m['role']}] {str(m.get('content'))[:100]}")
    print(f"[回答] {a}")


# ---- 工具级（不经 LLM）----

def test_calculator():
    r = run_tool("calculator", '{"expr": "(12+8)*3"}')
    print(f"\n=== 场景：calculator ===\n{r}")
    assert r == {"result": 60.0}
    assert "error" in run_tool("calculator", '{"expr": "__import__(\'os\').getcwd()"}')  # 注入被拒绝


def test_todo(env):
    run_tool("todo", '{"action": "add", "item": "查天气"}')
    run_tool("todo", '{"action": "done", "item": "查天气"}')
    r = run_tool("todo", '{"action": "list"}')
    print(f"\n=== 场景：todo ===\n{r}")
    assert r["todos"] == [{"item": "查天气", "status": "done"}]
    assert env.joinpath(".todo.json").exists()          # 持久化落盘


def test_registration():
    names = {t["function"]["name"] for t in schemas()}
    print(f"\n=== 场景：工具注册 ===\n已注册: {sorted(names)}")
    assert {"calculator", "todo", "search", "read_docs"} <= names
    todo_schema = next(t for t in schemas() if t["function"]["name"] == "todo")
    assert set(todo_schema["function"]["parameters"]["properties"]) == {"action", "item"}


# ---- 循环行为（真模型，回答人工判断，结构自动检查）----

def test_conversation_and_followup(env):
    """功能：纯对话 + 多轮记住状态。"""
    s = SessionManager().get("chat")
    a1 = good(run(s, "用一句话介绍 MiniAgent 这个项目"))
    a2 = good(run(s, "你刚才介绍了什么？"))               # 纯对话追问
    show("纯对话与追问", s, a2)
    assert [m["role"] for m in s.messages] == ["system", "user", "assistant", "user", "assistant"]


def test_tool_round_and_trace(env):
    """功能：模型自主决策调用 calculator，结果回传进历史，trace 完整。"""
    s = SessionManager().get("calc")
    a = good(run(s, "请用 calculator 工具计算 (12+8)*3"))
    show("工具调用 calculator", s, a)
    assert any(m["role"] == "tool" for m in s.messages)
    events = [json.loads(l)["event"]
              for l in (env / "logs" / "trace.jsonl").read_text("utf-8").splitlines()]
    assert events == ["llm", "tool", "llm"]               # trace 顺序：决策→执行→回答


def test_todo_flow(env):
    """功能：todo 工具真实落盘 + 带工具的追问。"""
    s = SessionManager().get("todo")
    a1 = good(run(s, "请用 todo 工具记一个待办：买牛奶"))
    assert "买牛奶" in (env / ".todo.json").read_text("utf-8")   # 落盘是工具行为，可自动判定
    a2 = good(run(s, "我刚记了什么待办？"))
    show("todo 与追问", s, a2)


def test_error_recovery(env):
    """功能：工具异常以 error 回传，agent 不崩溃并自行恢复。"""
    s = SessionManager().get("err")
    a = good(run(s, "请用 calculator 工具计算 1/0"))
    show("异常恢复", s, a)
    tool_msgs = [m for m in s.messages if m["role"] == "tool"]
    assert tool_msgs and "error" in tool_msgs[0]["content"]


def test_session_isolation(env):
    """功能：多 session 隔离 + 重启重放恢复。"""
    mgr = SessionManager()
    good(run(mgr.get("w1"), "用一句话介绍 Python"))
    good(run(mgr.get("w2"), "用一句话介绍围棋"))
    show("双窗口隔离", mgr.get("w1"), "(见各窗口回答)")
    w1 = json.dumps(mgr.get("w1").messages, ensure_ascii=False)
    w2 = json.dumps(mgr.get("w2").messages, ensure_ascii=False)
    assert "围棋" not in w1 and "介绍围棋" not in w1       # 窗口互不串话
    assert "介绍 Python" not in w2
    assert len(SessionManager().get("w1").messages) == len(mgr.get("w1").messages)  # 重放恢复


def test_scenario_search_and_docs(env):
    """功能：search 检索 + read_docs 阅读（检索工具闭环）。"""
    s = SessionManager().get("docs")
    a = good(run(s, "帮我查一下有没有天气相关的资料"))
    show("检索工具", s, a)
    assert any(m["role"] == "tool" for m in s.messages)


# ---- 结构性守卫 ----

def test_scenario_compaction(env):
    """功能：上下文超阈值自动压缩，system 与近期原文保留（摘要由当前模型生成）。"""
    s = SessionManager().get("compact")
    s.append({"role": "system", "content": "你是 MiniAgent。"})
    for i in range(30):
        s.append({"role": "user", "content": f"历史消息 {i} " + "x" * 200})
        s.append({"role": "assistant", "content": f"回复 {i} " + "y" * 200})
    assert maybe_compact(s, threshold=1000, keep_recent=6)
    print(f"\n=== 场景：上下文压缩 ===\n压缩后 {len(s.messages)} 条：")
    for m in s.messages[:2]:
        print(f"[{m['role']}] {str(m.get('content'))[:80]}")
    assert len(s.messages) == 8                            # system + 摘要 + 近 6 条
    assert s.messages[0]["role"] == "system"
    assert "[早期对话摘要]" in s.messages[1]["content"]
    assert "历史消息 27" in s.messages[2]["content"]        # 近期原文保留
    assert len(s.path.read_text("utf-8").splitlines()) == 8


def test_scenario_max_turns(env, monkeypatch):
    """功能：最大轮次守卫，超限优雅退出（置 0 直接触发，不调用模型）。"""
    monkeypatch.setattr(runtime, "MAX_TURNS", 0)
    out = run(SessionManager().get("turns"), "随便说点什么")
    print(f"\n=== 场景：最大轮次守卫 ===\n{out}")
    assert "最大轮次" in out
