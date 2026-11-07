# AI Prompt 与问题解决记录

记录本题开发过程中 AI（ZCode / GLM）的使用方式：什么交给 AI、什么自己决策、
遇到了什么问题、如何解决。

## 1. 调研阶段：用 AI 做资料汇总，不做方案决策

- Prompt（给 4 个并行研究代理）：分别调研「最小 agent loop 开源实现」「session 与
  context 压缩开源实现」「Memory 框架召回与放置」「Runtime 架构对比素材」，
  要求每项给出可验证链接与可抄做法。
- 产出：`../题目解读与开源方案调研.md`。自己决策：只取 Anthropic stop-reason 循环、
  Claude Code JSONL session/auto-compact/TodoWrite、pydantic-ai schema 自动推导
  五个设计，其余（OTel、流式、并行工具、多模态）判为题目外冗余砍掉。

## 2. 计划阶段：用 AI 把调研压成方案

- Prompt：写精简方案计划，最大程度参考已调研开源项目并做减法，代码要少，
  不写防御式编程。
- 产出：`../VibeCoding方案计划.md`。关键决策：总行数预算 ~700、全项目仅 2 处
  try/except（工具执行、LLM 调用——这是题目"基本异常处理"的全部语义）、消息全程
  plain dict 与 openai SDK 零转换。

## 3. 实现阶段的问题与解决

1. **pip 安装失败**：默认源（清华镜像 + pytorch cu124 extra-index）对 openai 包
   连接被重置。解决：`pip install -i https://pypi.org/simple openai pytest` 强制官方源。
2. **压缩后"保留近期消息"的断言算错**：61 条消息、keep_recent=6 时，recent 首条
   是 index 55（"历史消息 27"），初版断言写成 24。修测试断言，代码本身正确。
3. **追问用例调用次数算错**：首轮"调工具→回答"需要 2 次 LLM 调用，加上追问轮
   共 3 次，初版断言 2 次。修正为 3 并把断言指向第 3 次调用。
4. **设计取舍**：session 压缩后如何让重启不"复活"全量历史？若只改内存，JSONL 重放
   会还原全量。解决：给 Session 加 `rewrite()`（4 行），压缩后整体重写文件，
   正常对话仍走追加写。trace 日志独立保留全量事件，可审计。
5. **思考过程放哪**：GLM/DeepSeek 的 reasoning_content 单独提取进 dict 并入
   trace 日志展示，但不回传进历史（协议要求仅最后一轮 thinking 需回传，
   demo 中不做多轮思考回传，避免 context 膨胀）。

## 4. 验证方式

- `python -m pytest -q`：12 用例全绿（工具、注册、循环分支、隔离、追问、压缩、
  异常恢复、最大轮次、重放恢复、trace 顺序）。
- 冒烟：`python cli.py --help`、`import agent.runtime` + `schemas()` 列出 4 工具。
- 真实 LLM 联调：设置环境变量后 REPL 手工验证（仓库不含 key，提交前 `grep -r sk-` 复查）。


## 5. 真实 API 联调结果（2026-11-07）

- 服务：OpenAI-compatible 第三方接入，模型 cn:deepseek-v4.1-flash（key 仅环境变量）。
- 冒烟脚本 smoke_live.py 六项全部 PASS：纯对话 / calculator / todo / 追问带历史 / 独立 session / 隔离。
- trace.jsonl 证据（live-chat 会话）：
  - calculator：turn 0 模型发起 tool_call calculator({expr: "(12+8)*3"}) -> 执行 -> turn 1 回答 60——确认走真实工具调用而非心算；
  - todo：turn 0 调 add 写入 -> turn 1 确认；追问轮模型主动调 list 核实后再回答（agentic 行为）；
  - 每个任务恰好 2 次 LLM 调用（决策轮 + 回答轮），stop_reason/tool_calls 分支全部按设计工作；
  - 独立 session 对天气问题诚实回答无该能力，且与 live-chat 无串话。
- token 用量：input 6425 / output 676（约 7 次 LLM 调用）。
- 未在真实链路触发的能力由单测覆盖：上下文压缩（阈值未到）、工具异常恢复、最大轮次。
