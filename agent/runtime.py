"""Agent Runtime 主循环（题目四步一一对应）：

    Step 1  接收用户输入          -> session.append(user)
    Step 2  判断回复还是调工具     -> LLM 按 tool Schema 自主决策（tool_calls 有无）
    Step 3  调用工具              -> run_tool，结果回传
    Step 4  根据工具结果继续或返回  -> 无 tool_calls 即最终答案，退出循环
"""
import json
import os

from agent import llm, trace
from agent.context import maybe_compact
from agent.tools import run_tool, schemas

MAX_TURNS = int(os.environ.get("AGENT_MAX_TURNS", "20"))

SYSTEM_PROMPT = ("你是 MiniAgent。可调用工具完成任务，需要多步就逐步调用；"
                 "工具返回 error 时请修正参数重试或换方案；完成后用中文给出最终答复。")


def run(session, user_input):
    """处理一条用户输入（含追问），返回最终答复文本。"""
    if not session.messages:
        session.append({"role": "system", "content": SYSTEM_PROMPT})
    session.append({"role": "user", "content": user_input})            # Step 1
    for turn in range(MAX_TURNS):
        try:                                                           # 两处 try/except 之二
            msg = llm.chat(session.messages, schemas())                # Step 2
        except Exception as e:
            return f"LLM 调用失败: {type(e).__name__}: {e}"
        trace.log(session.sid, "llm", turn=turn, content=msg.get("content"),
                  tool_calls=msg.get("tool_calls"), thinking=msg.get("reasoning_content"))
        if not msg.get("tool_calls"):                                  # Step 4 最终答案
            session.append(msg)
            return msg["content"] or ""
        session.append(msg)
        for tc in msg["tool_calls"]:                                   # Step 3 调工具
            name, args = tc["function"]["name"], tc["function"]["arguments"]
            result = run_tool(name, args)
            trace.log(session.sid, "tool", turn=turn, tool=name, args=args, result=result)
            session.append({"role": "tool", "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False)})
        maybe_compact(session)                                         # 轮末检查压缩
    return "已达最大轮次限制。以上为当前进展，可开新会话或拆小任务后继续。"
