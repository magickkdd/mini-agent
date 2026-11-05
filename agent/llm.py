"""LLM 出口：OpenAI-compatible chat.completions。

key/base_url/模型只从环境变量读取，代码与仓库零密钥：
    OPENAI_API_KEY / OPENAI_BASE_URL / AGENT_MODEL
"""
import os

from openai import OpenAI

usage = {"input": 0, "output": 0}
_client = None


def chat(messages, tools=None):
    """调用一次 LLM，返回 assistant 消息 dict（content / reasoning_content / tool_calls）。
    统一转成普通 dict，上层（runtime/测试/FakeLLM）零转换复用。"""
    global _client
    if _client is None:
        _client = OpenAI()  # 自动读 OPENAI_API_KEY、OPENAI_BASE_URL
    kwargs = {"model": os.environ.get("AGENT_MODEL", "gpt-4o-mini"), "messages": messages}
    if tools:
        kwargs["tools"] = tools
    resp = _client.chat.completions.create(**kwargs)
    m = resp.choices[0].message
    u = resp.usage
    usage["input"] += u.prompt_tokens
    usage["output"] += u.completion_tokens
    out = {"role": "assistant", "content": m.content}
    if getattr(m, "reasoning_content", None):  # 思考过程（GLM/DeepSeek 等返回）
        out["reasoning_content"] = m.reasoning_content
    if m.tool_calls:
        out["tool_calls"] = [{"id": t.id, "type": "function",
                              "function": {"name": t.function.name,
                                           "arguments": t.function.arguments}}
                             for t in m.tool_calls]
    return out
