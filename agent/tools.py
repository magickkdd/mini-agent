"""工具注册机制 + 4 个工具。

@tool 从函数签名与 docstring 自动生成 JSON Schema（pydantic-ai auto 模式的极简版），
LLM 基于 Schema 自主决策调用。todo 规格取自 Claude Code TodoWrite：文件持久化、
状态简单明确。
"""
import ast
import inspect
import json
import operator
from pathlib import Path

TOOLS = {}  # name -> {"fn": callable, "schema": tool 定义}


def tool(fn):
    types = {"int": "integer", "float": "number", "bool": "boolean", "str": "string"}
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        props[name] = {"type": types.get(getattr(p.annotation, "__name__", "str"), "string")}
        if p.default is inspect.Parameter.empty:
            required.append(name)
    TOOLS[fn.__name__] = {
        "fn": fn,
        "schema": {"type": "function", "function": {
            "name": fn.__name__,
            "description": inspect.getdoc(fn) or "",
            "parameters": {"type": "object", "properties": props, "required": required}}},
    }
    return fn


def schemas():
    return [t["schema"] for t in TOOLS.values()]


def run_tool(name, args_json):
    """全项目两处 try/except 之一：工具报错转成 {"error": ...} 回传，由 LLM 自行修正。"""
    try:
        result = TOOLS[name]["fn"](**json.loads(args_json))
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    return result if isinstance(result, dict) else {"result": result}


# ---- calculator：ast 白名单遍历，禁 eval（安全求值的最小实现） ----
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv}
_UOPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
        return _OPS[type(n.op)](_ev(n.left), _ev(n.right))
    if isinstance(n, ast.UnaryOp) and type(n.op) in _UOPS:
        return _UOPS[type(n.op)](_ev(n.operand))
    raise ValueError(f"表达式含不支持的元素: {type(n).__name__}")


@tool
def calculator(expr: str):
    """计算数学表达式，如 "(1+2)*3/4"。expr 为表达式字符串。"""
    return round(float(_ev(ast.parse(expr, mode="eval").body)), 10)


# ---- todo：Claude Code TodoWrite 极简版（文件持久化、全量更新） ----
TODO_PATH = Path(__file__).resolve().parent.parent / ".todo.json"


def _load():
    return json.loads(TODO_PATH.read_text("utf-8")) if TODO_PATH.exists() else []


def _save(items):
    TODO_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), "utf-8")


@tool
def todo(action: str, item: str = ""):
    """管理待办清单。action="add" 添加一条（item=内容）；action="done" 把第一条包含
    item 的 pending 项标记完成；action="list" 返回全部待办。"""
    items = _load()
    if action == "add":
        items.append({"item": item, "status": "pending"})
        _save(items)
        return {"added": item, "todos": items}
    if action == "done":
        for t in items:
            if t["status"] == "pending" and item in t["item"]:
                t["status"] = "done"
                _save(items)
                return {"done": t["item"], "todos": items}
        return {"error": f"没有匹配的待办: {item}"}
    if action == "list":
        return {"todos": items}
    return {"error": f"未知 action: {action}"}


# ---- search / read_docs：mock 数据，二者形成"检索->阅读"闭环 ----
_DOCS = {
    "weather.md": "广州今日多云，26°C，东南风3级，湿度75%；厦门晴，29°C。",
    "agent.md": "MiniAgent 是一个约七百行实现的最小可用 Agent：LLM 循环 + 工具调用 + 会话持久化 + 上下文压缩。",
    "company.md": "省心购（广州）与光辰（厦门）是同一家公司，沟通一个即可。",
}


@tool
def search(query: str):
    """按关键词搜索内置文档，返回命中的文档名列表，可再用 read_docs 读全文。"""
    words = query.split()
    hits = [n for n, text in _DOCS.items() if any(w in text or w in n for w in words)]
    return {"hits": hits, "note": "未命中可换关键词，或用 read_docs 直接读取" if not hits else ""}


@tool
def read_docs(name: str):
    """读取内置文档全文。name 为文档名，可来自 search 的结果。"""
    if name not in _DOCS:
        return {"error": f"文档不存在: {name}"}
    return {"doc": name, "content": _DOCS[name]}
