"""7 类用例：工具、注册、循环分支、session 隔离、追问、压缩、异常恢复/最大轮次/trace。

全部用 FakeLLM 剧本回放：确定性、零 token、CI 可跑。
"""
import json

import agent.runtime as runtime
from agent.context import maybe_compact
from agent.runtime import run
from agent.session import SessionManager
from agent.tools import TOOLS, run_tool, schemas
from fake_llm import FakeLLM, answer, call_tool


# 1. 工具：calculator 安全求值 + 非法输入报错
def test_calculator(env):
    assert run_tool("calculator", '{"expr": "1+2*3"}') == {"result": 7.0}
    assert run_tool("calculator", '{"expr": "(2-4)*0.5"}') == {"result": -1.0}
    r = run_tool("calculator", '{"expr": "__import__(\'os\').getcwd()"}')
    assert "error" in r  # 白名单外元素（Call 节点）被拒绝


# 2. 工具：todo 增改查 + 文件持久化
def test_todo(env):
    run_tool("todo", '{"action": "add", "item": "查天气"}')
    run_tool("todo", '{"action": "add", "item": "写周报"}')
    r = run_tool("todo", '{"action": "done", "item": "查天气"}')
    assert r["done"] == "查天气"
    r = run_tool("todo", '{"action": "list"}')
    assert r["todos"] == [{"item": "查天气", "status": "done"},
                          {"item": "写周报", "status": "pending"}]
    assert env.joinpath(".todo.json").exists()  # 持久化落盘


# 3. 注册机制：名称/描述/参数 Schema 齐全
def test_registration():
    assert {"calculator", "todo", "search", "read_docs"} <= set(TOOLS)
    for t in schemas():
        f = t["function"]
        assert t["type"] == "function" and f["description"] and f["parameters"]["properties"]
    todo_schema = next(t for t in schemas() if t["function"]["name"] == "todo")
    assert set(todo_schema["function"]["parameters"]["properties"]) == {"action", "item"}
    assert todo_schema["function"]["parameters"]["required"] == ["action"]


# 4. 主循环分支一：直接回复（Step 2 -> Step 4 出口）
def test_loop_direct(fake, env):
    f = fake(answer("你好！有什么可以帮你？"))
    s = SessionManager().get("t1")
    assert run(s, "你好") == "你好！有什么可以帮你？"
    assert [m["role"] for m in s.messages] == ["system", "user", "assistant"]
    assert f.calls[0][0]["role"] == "system" and f.calls[0][1]["role"] == "user"


# 5. 主循环分支二：调工具后回答（Step 2 -> Step 3 -> Step 4）
def test_loop_tool(fake, env):
    f = fake(call_tool("c1", "calculator", expr="1+2*3"), answer("1+2*3 等于 7"))
    s = SessionManager().get("t2")
    assert run(s, "帮我算 1+2*3") == "1+2*3 等于 7"
    roles = [m["role"] for m in s.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    assert "7" in s.messages[3]["content"]
    events = [json.loads(line)["event"] for line in (env / "logs" / "trace.jsonl").read_text("utf-8").splitlines()]
    assert events == ["llm", "tool", "llm"]  # trace 顺序：LLM 决策 -> 工具执行 -> LLM 回答


# 6. session 隔离：两个"窗口"历史互不污染
def test_session_isolation(fake, env):
    mgr = SessionManager()
    fake(answer("窗口1：广州今日多云 26°C"))
    a1 = run(mgr.get("win1"), "查广州天气")
    fake(answer("窗口2：周报已写好"))
    a2 = run(mgr.get("win2"), "写周报")
    assert a1.startswith("窗口1") and a2.startswith("窗口2")
    assert "周报" not in str(mgr.get("win1").messages)
    assert "天气" not in str(mgr.get("win2").messages)
    assert mgr.get("win1").path.exists() and mgr.get("win2").path.exists()


# 7. 追问（带工具 + 纯对话）：同一 session 历史自然带入下轮 context
def test_followup(fake, env):
    f = fake(call_tool("c1", "todo", action="add", item="买牛奶"),
             answer("已记下待办：买牛奶"))
    s = SessionManager().get("t5")
    run(s, "记个待办：买牛奶")
    f.script.append(answer("你刚记的待办是：买牛奶（pending）"))  # 第二轮剧本
    assert run(s, "我刚记了什么待办？") == "你刚记的待办是：买牛奶（pending）"
    # 共 3 次调用：首轮工具决策、首轮最终回答、追问轮
    assert len(f.calls) == 3
    assert any("买牛奶" in str(m) for m in f.calls[2])  # 首轮工具结果保留在历史里


# 8. 上下文压缩：超阈值触发摘要替换，system 与近 K 条保留，会话文件同步重写
def test_compaction(fake, env):
    fake(answer("摘要：用户在准备笔试；已查天气；未决事项：无"))
    s = SessionManager().get("t6")
    s.append({"role": "system", "content": "你是 MiniAgent。"})
    for i in range(30):
        s.append({"role": "user", "content": f"历史消息 {i} " + "x" * 200})
        s.append({"role": "assistant", "content": f"回复 {i} " + "y" * 200})
    assert maybe_compact(s, threshold=1000, keep_recent=6)
    assert len(s.messages) == 8  # system 1 + 摘要 1 + 近期 6
    assert s.messages[0]["role"] == "system"
    assert "[早期对话摘要]" in s.messages[1]["content"]
    assert "历史消息 27" in s.messages[2]["content"]  # 近期原文保留（recent 首条=index 55）
    assert len(s.path.read_text("utf-8").splitlines()) == 8  # 文件已重写为压缩态
    assert not maybe_compact(s, threshold=1000, keep_recent=6)  # 已低于阈值不再触发


# 9. 异常恢复：工具报错回传 LLM，agent 不崩并继续作答
def test_tool_error_recovery(fake, env):
    fake(call_tool("c1", "calculator", expr="1/0"),
         answer("除以零无法计算，请换一个表达式。"))
    s = SessionManager().get("t7")
    assert run(s, "算 1/0") == "除以零无法计算，请换一个表达式。"
    assert "error" in json.loads(s.messages[3]["content"])  # ZeroDivisionError 已回传


# 10. 最大轮次：耗尽后优雅退出而非崩溃
def test_max_turns(fake, env, monkeypatch):
    monkeypatch.setattr(runtime, "MAX_TURNS", 2)
    fake(*[call_tool(f"c{i}", "search", query=f"q{i}") for i in range(5)])
    s = SessionManager().get("t8")
    assert "最大轮次" in run(s, "一直搜下去")


# 11. 持久化恢复：重启（新 SessionManager）后历史完整重放
def test_session_reload(fake, env):
    fake(call_tool("c1", "todo", action="add", item="复盘"), answer("已记录"))
    mgr = SessionManager()
    run(mgr.get("t9"), "记待办：复盘")
    s2 = SessionManager().get("t9")  # 模拟重启
    assert len(s2.messages) == len(mgr.get("t9").messages)
    assert any("复盘" in json.dumps(m, ensure_ascii=False) for m in s2.messages)


# 12. FakeLLM 剧本耗尽必须显性失败（防测试假绿）
def test_fake_llm_exhausted(env):
    f = FakeLLM()
    try:
        f.chat([{"role": "user", "content": "hi"}])
        assert False, "应抛出 AssertionError"
    except AssertionError as e:
        assert "剧本已耗尽" in str(e)
