"""按剧本回放的假 LLM：chat() 依次弹出脚本中的 assistant 消息 dict，并记录每次收到的 messages。"""
import json


class FakeLLM:
    def __init__(self, *script):
        self.script = list(script)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append(list(messages))
        assert self.script, "剧本已耗尽但仍在调用 LLM"
        return self.script.pop(0)


def answer(text):
    """直接给最终答案的消息。"""
    return {"role": "assistant", "content": text}


def call_tool(id, name, **args):
    """发起一次工具调用的消息。"""
    return {"role": "assistant", "content": None,
            "tool_calls": [{"id": id, "type": "function",
                            "function": {"name": name,
                                         "arguments": json.dumps(args, ensure_ascii=False)}}]}
