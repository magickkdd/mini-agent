"""真实 API 联调冒烟脚本：配置好环境变量后运行 `python smoke_live.py`。

前置（任意 OpenAI-compatible 服务均可）：
    export OPENAI_API_KEY=sk-xxx
    export OPENAI_BASE_URL=https://...        # 可选，GLM/豆包/DeepSeek 等
    export AGENT_MODEL=glm-4.7                # 可选，默认 gpt-4o-mini

跑五项真实链路检查并打印 PASS/FAIL 清单。
"""
import json
import shutil

from agent import llm, trace
from agent.runtime import run
from agent.session import SessionManager

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("  -> " + str(detail)[:120] if detail else ""))


# 0. 环境自检
import os
assert os.environ.get("OPENAI_API_KEY"), "请先设置 OPENAI_API_KEY 环境变量"
print("model =", os.environ.get("AGENT_MODEL", "gpt-4o-mini（默认）"),
      "| base_url =", os.environ.get("OPENAI_BASE_URL", "官方默认"))

# 1. 纯对话
s1 = SessionManager().get("live-chat")
a1 = run(s1, "用一句话介绍你自己")
check("纯对话", bool(a1 and a1.strip()), a1)

# 2. 工具调用（calculator）
a2 = run(s1, "帮我计算 (12+8)*3 等于多少，用计算器工具")
check("工具调用 calculator", "60" in a2, a2)

# 3. todo 工具 + 持久化
a3 = run(s1, "记个待办：给笔试题写 README")
check("todo 工具", ("待办" in a3 or "记" in a3), a3)

# 4. 追问（历史带入）
a4 = run(s1, "我刚才让你记的待办是什么？")
check("追问带历史", ("README" in a4 or "笔试" in a4), a4)

# 5. session 隔离
a5 = run(SessionManager().get("live-other"), "今天天气怎么样？随便聊聊")
check("独立 session 可用", bool(a5 and a5.strip()), a5)

msgs = SessionManager().get("live-chat").messages
check("live-chat 与 live-other 互不串话",
      all("天气" not in json.dumps(m, ensure_ascii=False) for m in msgs))

print("\n--- 汇总 ---")
for name, ok, _ in results:
    print(("PASS " if ok else "FAIL ") + name)
print(f"\n[tokens 累计] input={llm.usage['input']} output={llm.usage['output']}")
print("[trace 日志] logs/trace.jsonl 最后 3 条：")
log = trace.LOG_PATH
if log.exists():
    for line in log.read_text("utf-8").splitlines()[-3:]:
        print("  " + line[:160])
print("\n结果：" + ("全部通过" if all(ok for _, ok, _ in results) else "存在失败项，见上表"))
