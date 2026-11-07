# MiniAgent

MiniAgent 是一个**从零实现**的最小可用 agent harness（智能体运行时），为本仓库作者参加 2026 年 Agent harness 技术笔试题开发并开源。

它构建于 **stop-reason 驱动的主循环**之上，不依赖任何 agent 框架（langgraph / openhands 等），仅使用 `openai` SDK 作为 HTTP 客户端，兼容 GLM / 豆包 / DeepSeek 等一切 OpenAI-compatible 服务。全部代码（含测试）约 520 行，每个文件都可以一次读完。设计遵循 Anthropic《Building effective agents》的原则：先手写 API，慎用抽象层。

## 状态

笔试交付版本。核心运行时（主循环、工具注册、session、上下文压缩、trace）已通过 12 项确定性测试；流式输出、并行工具调用、多模态等能力按题目范围刻意不做，演进方向见「路线图」。

## 安全说明

- API key 只从环境变量读取，代码与仓库零密钥；
- calculator 使用 AST 白名单求值，从语言层面拒绝代码注入；
- 不提供任何 shell / 任意文件写入工具，工具面最小化。

<a id="run"></a>

## 运行

### 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 是 | 密钥，只放环境变量，不入仓库 |
| `OPENAI_BASE_URL` | 否 | 指向 GLM / 豆包 / DeepSeek 等，缺省为 OpenAI 官方 |
| `AGENT_MODEL` | 否 | 模型名，默认 `gpt-4o-mini` |
| `AGENT_MAX_TURNS` | 否 | 单次任务最大轮数，默认 20 |
| `AGENT_COMPACT_THRESHOLD` | 否 | 上下文压缩触发阈值（token 估算），默认 3000 |

### 启动 REPL

安装依赖后运行：

```sh
pip install -r requirements.txt
python cli.py --session work1
```

`--session` 指定会话 ID：另开一个终端运行 `python cli.py --session work2`，即得到互不影响的第二个窗口；退出重进自动从 `sessions/<sid>.jsonl` 恢复历史，随时接着聊。

### 真实链路冒烟

```sh
python smoke_live.py
```

依次检查纯对话、calculator、todo、追问带历史、双 session 隔离五项真实链路，并打印 token 用量与 trace 日志尾部。

## 测试

```sh
python -m pytest -q
```

12 个用例全部基于 FakeLLM 剧本回放：确定性、零 token、CI 可跑，覆盖循环分支、session 隔离、追问、上下文压缩、异常恢复、最大轮次与会话重放。

## 系统设计

```
cli.py ──▶ runtime.run()  主循环
            │  Step 1 接收输入 → 追加 user 消息
            │  Step 2 LLM 决策（按工具 Schema；无 tool_calls = 最终答案 → 返回）
            │  Step 3 调工具（报错以 {"error"} 回传，由 LLM 自行修正）
            │  Step 4 轮末 maybe_compact 压缩检查；超 MAX_TURNS 优雅退出
            ├─ llm.py       唯一 LLM 出口，SDK 消息统一转 plain dict
            ├─ tools.py     @tool 装饰器自动生成 JSON Schema + 4 个工具
            ├─ session.py   dict[sid]→Session，JSONL 追加持久化、重启重放
            ├─ context.py   token 估算 + 阈值触发 LLM 摘要压缩
            └─ trace.py     logs/trace.jsonl 全量执行日志
```

| 模块 | 职责 |
|---|---|
| `agent/runtime.py` | 主循环、MAX_TURNS 计数、压缩检查、LLM 失败兜底 |
| `agent/llm.py` | LLM 调用、reasoning_content 提取、usage 统计 |
| `agent/tools.py` | 注册机制；calculator（AST 白名单）/ todo（TodoWrite 规格）/ search / read_docs |
| `agent/session.py` | 多 session 隔离、JSONL 追加、重启重放、压缩后整体重写 |
| `agent/context.py` | token 估算、摘要压缩、保留近 K 条原文 |
| `agent/trace.py` | JSONL 执行日志（LLM 调用 / 工具执行 / 压缩事件） |

设计对照（在成熟开源方案之上做减法）：主循环取 Anthropic《Building effective agents》的 stop-reason 模式；session 与压缩取 Claude Code（JSONL 转写文件 / auto-compact）；工具 Schema 自动推导取 pydantic-ai 极简版；todo 规格取 Claude Code TodoWrite；异常恢复取 Anthropic is_error 模式（报错回传 LLM 自行修正）。

### Memory 的召回时机与放置方式

- **会话开始召回一次**：`SessionManager.get` 从 JSONL 重放该窗口全部历史，等价于一次性召回窗口记忆，成本固定；
- **每轮常驻**：最近对话原文常驻 context，两类追问（纯文本 / 带工具）无需任何额外机制；
- **按需深查（agentic recall）**：LLM 可主动调用 `todo list` / `read_docs` / `search` 自主决定何时取记忆，避免每轮全量检索；
- **放置方式**：跨窗口持久记忆放文件（`.todo.json`、`sessions/*.jsonl`）；进 context 走两条路——常驻（system prompt / 重放历史，占固定 token）与按需（工具结果作为 tool 消息进入，零常驻成本）；
- **扩展路径**：跨 session 长期记忆在会话开始按 user_id 检索相关事实注入 system prompt（Mem0 做法），同时提供 `memory_search` 工具按需深查，并以新替旧做冲突更新（Graphiti 语义）。

## 项目结构

```
mini-agent/
├── agent/
│   ├── runtime.py      # 主循环（约 55 行）
│   ├── llm.py          # LLM 出口（约 45 行）
│   ├── tools.py        # 注册机制 + 4 个工具（约 130 行）
│   ├── session.py      # session 隔离与持久化（约 50 行）
│   ├── context.py      # 上下文压缩（约 40 行）
│   └── trace.py        # 执行日志（约 18 行）
├── cli.py              # REPL 客户端（约 35 行）
├── smoke_live.py       # 真实 API 冒烟脚本
├── tests/              # FakeLLM + 12 个用例（约 220 行）
├── README.md
├── AI_PROMPTS.md       # AI 使用与问题解决记录
└── requirements.txt
```

## 路线图

- 真实模型联调（`smoke_live.py` 已就绪，配置环境变量即可运行）；
- 跨 session 长期记忆（`memory_search` 工具 + 冲突更新）；
- 异步工具与完成通知、流式输出。

## 引用

```bibtex
@misc{miniagent2026,
  title={MiniAgent: A Minimal Agent Harness in About 500 Lines},
  author={MiniAgent contributors},
  year={2026},
  publisher={GitHub},
  howpublished={\url{https://github.com/mini-agent/mini-agent}},
}
```

## 许可证

[MIT](LICENSE)
