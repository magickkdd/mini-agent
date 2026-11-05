"""上下文压缩（Claude Code auto-compact 极简版）。

token 估算超阈值时：旧消息交给 LLM 压成一条摘要（保留目标/偏好/已做/未决），
最近 keep_recent 条消息保留完整原文，并重写会话文件使重启后仍为压缩态。
"""
import json
import os

from agent import llm, trace


def estimate_tokens(messages):
    """粗估 1 token ≈ 4 字符，够用即可。"""
    return sum(len(json.dumps(m, ensure_ascii=False)) for m in messages) // 4


def maybe_compact(session, threshold=None, keep_recent=None):
    threshold = threshold or int(os.environ.get("AGENT_COMPACT_THRESHOLD", "3000"))
    keep_recent = keep_recent or 6
    if len(session.messages) <= keep_recent or estimate_tokens(session.messages) < threshold:
        return False
    old, recent = session.messages[:-keep_recent], session.messages[-keep_recent:]
    system = [old[0]] if old[0]["role"] == "system" else []
    body = old[len(system):]
    if not body:
        return False
    prompt = [{"role": "user", "content":
        "请将以下对话历史压缩为一段摘要，必须保留：用户目标与偏好、已完成动作及结果、未决事项。只输出摘要。\n\n"
        + "\n".join(json.dumps(m, ensure_ascii=False) for m in body)}]
    summary = llm.chat(prompt)["content"]
    session.messages[:] = system + [{"role": "user", "content": f"[早期对话摘要]\n{summary}"}] + recent
    session.rewrite()
    trace.log(session.sid, "compact", summarized=len(body), kept=len(recent))
    return True
