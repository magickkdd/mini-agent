# MiniAgent —— 从零实现的最小可用 Agent

笔试题「从零实现一个最小可用 Agent」的实现。核心 Agent Runtime 完全自研，
不依赖任何 agent 框架（langgraph/openhands 等）；唯一外部依赖是 `openai` SDK
（仅作 HTTP 客户端，非 agent 框架）。全部代码约 **640 行**（含测试），每个文件都短到可以一次读完。

## 运行方式

```bash
pip install -r requirements.txt

# 配置 LLM（key 只放环境变量，代码与仓库零密钥；兼容任何 OpenAI-compatible 服务）
export OPENAI_API_KEY=sk-xxx          # Windows: set OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://...    # 可选，指向 GLM/豆包/DeepSeek 等
export AGENT_MODEL=glm-4.7            # 可选，默认 gpt-4o-mini

# 窗口 1
python cli.py --session work1
# 窗口 2（另开一个终端）
python cli.py --session work2

# 运行测试（全部为 FakeLLM 剧本回放，确定性、零 token、无需 key）
python -m pytest -q
```

窗口 1 / 窗口 2 是两个独立 session：历史各自持久化在 `sessions/<sid>.jsonl`，
随时退出重进（`--session work1`）接着聊，互不影响。

内置工具：`calculator`（AST 白名单求值，禁 eval）、`todo`（待办清单，文件持久化）、
`search`（关键词检索内置文档，mock）、`read_docs`（读取文档全文，与 search 成闭环）。

## 系统设计

```
cli.py ──▶ runtime.run()  主循环
            │  Step 1 接收输入 → 追加 user 消息
            │  Step 2 LLM 决策（按工具 Schema；无 tool_calls = 最终答案 → 返回）
            │  Step 3 调工具（结果回传，报错以 {"error"} 回传让 LLM 自行修正）
            │  Step 4 轮末：maybe_compact 检查压缩；超 MAX_TURNS 优雅退出
            ├─ llm.py       唯一 LLM 出口，SDK 消息统一转 plain dict
            ├─ tools.py     @tool 装饰器自动生成 JSON Schema + 4 个工具
            ├─ session.py   dict[sid]→Session，JSONL 追加持久化、重启重放
            ├─ context.py   token 估算 + 阈值触发 LLM 摘要压缩
            └─ trace.py     logs/trace.jsonl：LLM 调用/工具执行/压缩 全量日志
```

设计对照成熟开源方案（在其之上做减法）：

| 设计点 | 参考方案 | 本实现的取舍 |
|---|---|---|
| 主循环 | Anthropic《Building effective agents》stop-reason 循环 | 保留：LLM→tool→loop，无 tool_calls 即出口 |
| 工具注册 | pydantic-ai auto schema | 40 行装饰器：签名+docstring 自动生成 Schema |
| todo 工具 | Claude Code TodoWrite（文件持久化、全量更新） | 状态简化为 pending/done |
| session | Claude Code 每 session 一个 JSONL 转写文件 | 相同：追加写、重启重放恢复 |
| 上下文压缩 | Claude Code auto-compact（阈值触发、摘要+近期原文保留） | 相同思路，threshold/keep_recent 可调 |
| 异常处理 | Anthropic is_error 模式 | 全项目仅 2 处 try/except：工具执行、LLM 调用 |
| 执行日志 | smolagents OpenTelemetry | 降为本地 JSONL，零依赖 |
| 测试 | inspect-ai/promptfoo 的"mock LLM"思路 | FakeLLM 剧本回放，12 个用例 |

哪些信息进 context（题目问答题）：system prompt 常驻；用户输入永不删；
工具结果以 `role=tool` 消息保留（超长会污染 context，生产中应截断）；assistant
的 reasoning_content 只入 trace 日志、不回传（GLM/DeepSeek 协议下无需回传历史思考）；
压缩时旧消息被摘要替换、最近 keep_recent 条保留完整原文。

## Memory 的召回时机与放置方式说明

本 demo 的 memory 即「session 持久化历史 + system prompt」，按业界主流（Mem0 的应用层惯例）设计召回与放置：

- **召回时机**：
  1. **会话开始时**召回一次——`SessionManager.get(sid)` 从 JSONL 重放全部历史，
     等价于把该用户此窗口的记忆一次性召回进 context，成本固定；
  2. **每轮自动在 context 中**——最近对话原文常驻，追问（纯文本或带工具）无需任何
     额外机制，新输入追加进 messages 即完成"带着记忆回复"；
  3. **按需深查**（agentic recall）——LLM 可主动调用 `todo list` / `read_docs` /
     `search` 等工具自主决定何时取记忆，避免每轮全量检索的 token 浪费。
- **放置方式**：跨窗口持久记忆放 **文件**（`.todo.json`、`sessions/*.jsonl`），
  进 context 的方式有两种——常驻（system prompt / 重放的历史，占固定 token）
  与按需（工具返回结果作为 tool 消息进入 context，零常驻成本）。
- 若扩展到跨 session 的长期记忆：在会话开始按 user_id 检索相关事实注入 system
  prompt（Mem0 做法），同时提供 `memory_search` 工具按需深查，并引入冲突更新
  （新旧事实矛盾时以新替旧，Graphiti/Mem0 的 UPDATE 语义）。

## 项目结构

```
mini-agent/
├── agent/
│   ├── llm.py        # LLM 出口（~45 行）
│   ├── tools.py      # 注册机制 + calculator/todo/search/read_docs（~130 行）
│   ├── session.py    # 多 session 隔离 + JSONL 持久化（~50 行）
│   ├── context.py    # token 估算 + 压缩（~40 行）
│   ├── trace.py      # JSONL 执行日志（~18 行）
│   └── runtime.py    # 主循环（~55 行）
├── cli.py            # REPL（~35 行）
├── tests/            # FakeLLM + 12 个用例（~220 行）
├── README.md / AI_PROMPTS.md / requirements.txt
```

## 已验证的验收对照

| 题目要求 | 实现位置 | 测试 |
|---|---|---|
| 基本循环四步 | agent/runtime.py | test_loop_direct / test_loop_tool |
| ≥3 工具含 todo | agent/tools.py | test_calculator / test_todo |
| 工具注册（名/描述/Schema） | agent/tools.py `@tool` | test_registration |
| 输出解析（思考/调用/答案） | agent/llm.py（reasoning_content/tool_calls/content） | test_loop_tool |
| session 隔离、随时续聊 | agent/session.py | test_session_isolation / test_session_reload |
| 最大轮次 | agent/runtime.py MAX_TURNS | test_max_turns |
| 纯对话 + 带工具追问 | messages 追加即追问 | test_followup |
| 基础压缩 | agent/context.py | test_compaction |
| 基本异常处理 | run_tool / runtime（仅 2 处 try/except） | test_tool_error_recovery / test_calculator |
| trace / 执行日志 | agent/trace.py | test_loop_tool（断言日志事件顺序） |
| 代码零 LLM API key | 全仓库（key 仅环境变量） | grep 可查 |

## 已知简化（题目允许范围内）

- 工具结果超长不截断（demo 数据可控）；压缩为单层摘要，无递归压缩。
- 不做流式输出、并行工具调用、多模态——题目未要求。
- search/read_docs 为 mock 数据，接口与真实检索一致。
