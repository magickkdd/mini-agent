# MiniAgent

从零实现的最小可用 Agent（约 520 行，不依赖任何 agent 框架），stop-reason 驱动主循环，兼容 GLM / 豆包 / DeepSeek 等一切 OpenAI-compatible 服务。

## 快速开始

### 1. 安装

```sh
pip install -r requirements.txt
```

### 2. 设置环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 是 | 你的 API key（只放环境变量，不入仓库） |
| `OPENAI_BASE_URL` | 否 | 服务商地址，如 GLM `https://open.bigmodel.cn/api/paas/v4`；不填走 OpenAI 官方 |
| `AGENT_MODEL` | 否 | 模型名，如 `glm-4.7` / `deepseek-chat`；不填默认 `gpt-4o-mini` |

Windows (PowerShell)：

```powershell
$env:OPENAI_API_KEY = "sk-xxx"
$env:OPENAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
$env:AGENT_MODEL = "glm-4.7"
```

Linux / macOS：

```sh
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
export AGENT_MODEL=glm-4.7
```

### 3. 使用

```sh
python cli.py --session work1   # 窗口 1
python cli.py --session work2   # 另开终端 = 窗口 2，与窗口 1 互不影响
```

- 直接输入问题对话，`exit` 退出；退出重进自动恢复历史（存于 `sessions/<sid>.jsonl`）。
- 内置工具：`calculator`（AST 白名单安全求值）、`todo`（待办清单，存 `.todo.json`）、`search` / `read_docs`（内置文档检索，mock 数据）。
- 可选变量：`AGENT_MAX_TURNS`（单任务最大轮数，默认 20）、`AGENT_COMPACT_THRESHOLD`（上下文压缩阈值，默认 3000）。

### 4. 测试与冒烟

```sh
python -m pytest -q        # 12 个用例，FakeLLM 剧本回放，零 token
python smoke_live.py       # 真实 API 冒烟：五项链路检查
```

## 系统设计

```
cli.py ─▶ runtime.run() 主循环：Step1 接收输入 ▶ Step2 LLM 决策（无 tool_calls 即最终答案）
         ▶ Step3 调工具（报错以 {"error"} 回传，LLM 自行修正）▶ Step4 轮末压缩检查 / 超轮次优雅退出
         ├─ llm.py     LLM 出口，SDK 消息统一转 plain dict
         ├─ tools.py   @tool 自动生成 JSON Schema + calculator / todo / search / read_docs
         ├─ session.py 每 session 一个 JSONL 转写文件，重启重放
         ├─ context.py token 超阈值 → 旧消息 LLM 摘要，保留近 6 条原文
         └─ trace.py   logs/trace.jsonl 全量执行日志
```

### Memory 的召回时机与放置方式

- **会话开始**：从 JSONL 重放该窗口全部历史（一次性召回，成本固定）；
- **每轮**：最近对话常驻 context，两类追问无需额外机制；
- **按需**：LLM 可调用 todo list / search / read_docs 主动查记忆（agentic recall）；
- **放置**：持久记忆在文件；进 context 两条路——常驻（system / 历史）与按需（tool 消息）；
- **扩展**：跨 session 长期记忆按 user_id 检索注入 system prompt（Mem0 式）+ memory_search 工具深查 + 冲突更新（Graphiti 式）。

## 许可证

[MIT](LICENSE)
