"""
MOMOKA HTTP API 服务器
提供 POST /api/chat、POST /api/judge 和静态文件服务。
"""

import json
import os
import asyncio
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
import uvicorn

from agents import Runner, trace

from file_agent import create_agent, skill_loader, memory_store
from momoka.config import LIKERT_LABELS
from momoka.skill_loader import format_skill_prompt

PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"


def check_config() -> dict:
    """检查并返回配置信息。"""
    issues = []
    info = {}

    api_key = os.environ.get("ALIYUN_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    if api_key:
        info["provider"] = "DashScope" if "ALIYUN_API_KEY" in os.environ else (base_url or "OpenAI")
        info["key_prefix"] = api_key[:8] + "..."
    else:
        issues.append("ALIYUN_API_KEY 未设置 — 请设置环境变量 ALIYUN_API_KEY（或回退 OPENAI_API_KEY）")

    info["skills_loaded"] = len(skill_loader.list_skills())
    return {"info": info, "issues": issues}


def extract_tool_calls(result) -> list[dict]:
    """从 Agent 运行结果中提取结构化的工具调用日志。"""
    tool_calls = []
    if not hasattr(result, "new_items"):
        return tool_calls

    current_call = None
    for item in result.new_items:
        if not hasattr(item, "raw_item"):
            continue
        raw = item.raw_item

        if hasattr(raw, "type") and raw.type == "function_call":
            current_call = {
                "tool": getattr(raw, "name", "unknown"),
                "args": getattr(raw, "arguments", "{}"),
                "result": "",
            }
        elif hasattr(raw, "type") and raw.type == "function_call_output":
            output = str(getattr(raw, "output", ""))
            if current_call:
                current_call["result"] = output[:500]
                tool_calls.append(current_call)
                current_call = None
            else:
                tool_calls.append({
                    "tool": "unknown",
                    "args": "{}",
                    "result": output[:500],
                })

    return tool_calls


async def api_chat(request: Request) -> JSONResponse:
    """处理聊天请求。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "请求体必须是 JSON"}, status_code=400)

    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)

    # 创建 Agent（含技能匹配 + 记忆注入）
    agent = create_agent(message)

    # 检测匹配的技能
    matched = skill_loader.match_skills(message)
    matched_names = [m["meta"]["name"] for m in matched]

    try:
        with trace("MOMOKA API"):
            result = await Runner.run(agent, message)
    except Exception as e:
        msg = str(e)
        if "api_key" in msg.lower() or "OPENAI_API_KEY" in msg or "ALIYUN_API_KEY" in msg:
            return JSONResponse({
                "error": "API key 未配置",
                "detail": "请设置环境变量 ALIYUN_API_KEY（或回退 OPENAI_API_KEY）",
                "tool_calls": [],
            }, status_code=503)
        return JSONResponse({
            "error": f"Agent 执行失败: {msg}",
            "tool_calls": [],
        }, status_code=500)

    tool_calls = extract_tool_calls(result)

    # 写入日记忆 (MOMOKA_PRD: 每次交互自动记录)
    memory_store.write_daily(
        f"**用户**: {message}\n**Agent**: {result.final_output[:300]}"
    )

    output_id = body.get("output_id", "")

    return JSONResponse({
        "output_id": output_id,
        "response": result.final_output,
        "tool_calls": tool_calls,
        "matched_skills": matched_names,
    })


async def api_judge(request: Request) -> JSONResponse:
    """处理用户的批注判断 (MOMOKA_PRD 核心交互: Likert 7 点量表)。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "请求体必须是 JSON"}, status_code=400)

    output_id = body.get("output_id", "")
    score = body.get("score", 0)
    context = body.get("context", "")

    if not isinstance(score, int) or score < 1 or score > 7:
        return JSONResponse({
            "error": "评分必须是 1-7 的整数",
            "valid_range": {str(k): v for k, v in LIKERT_LABELS.items()},
        }, status_code=400)

    label = LIKERT_LABELS.get(score, "未知")

    # 记录判断到短期召回存储
    memory_store.record_judgment(output_id, score, context)

    # 判断分析 (MOMOKA_PRD: Reflect 阶段)
    analysis = _analyze_judgment(score, label)

    # 写入日记忆
    memory_store.write_daily(
        f"**评分**: {score}/7 ({label})\n**分析**: {analysis}\n**上下文**: {context[:200]}"
    )

    return JSONResponse({
        "score": score,
        "label": label,
        "analysis": analysis,
    })


def _analyze_judgment(score: int, label: str) -> str:
    """分析用户判断的含义 (MOMOKA_PRD: Reflect 阶段)。"""
    if score <= 2:
        return f"方向偏离 — 需要重新理解用户意图，当前输出被判定为 '{label}'"
    elif score == 3:
        return f"接近但不足 — 方向基本正确，但需要细化或调整角度"
    elif score == 4:
        return "中立 — 用户有其他不冲突但不同的想法，需要发散探索新方向"
    elif score == 5:
        return f"方向正确 — 有改进空间，可在此基础上深化"
    else:  # 6-7
        return f"超出预期 — 当前方向完美匹配，可作为正面样本固化到技能库"


async def api_skills(_request: Request) -> JSONResponse:
    """返回已加载的技能列表。"""
    return JSONResponse({"skills": skill_loader.list_skills()})


async def api_memory(_request: Request) -> JSONResponse:
    """返回最近的记忆。"""
    return JSONResponse({
        "daily": memory_store.read_daily(7),
        "long_term": memory_store.read_long_term()[:2000],
    })


async def api_config(_request: Request) -> JSONResponse:
    """返回配置状态。"""
    return JSONResponse(check_config())


async def health(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("MOMOKA OK")


# 路由
routes = [
    Route("/api/health", health),
    Route("/api/config", api_config),
    Route("/api/chat", api_chat, methods=["POST"]),
    Route("/api/judge", api_judge, methods=["POST"]),
    Route("/api/skills", api_skills),
    Route("/api/memory", api_memory),
]

app = Starlette(routes=routes)

# 静态文件服务
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True))


def main():
    """启动服务器。"""
    print("MOMOKA HTTP Server 启动中...")
    cfg = check_config()
    if cfg["issues"]:
        for issue in cfg["issues"]:
            print(f"  [!] {issue}")
    else:
        print(f"  [OK] Provider: {cfg['info'].get('provider', '?')}")
        print(f"  [OK] Key: {cfg['info'].get('key_prefix', '?')}")
    print(f"  [OK] Skills: {cfg['info'].get('skills_loaded', 0)} loaded")
    print(f"  访问: http://localhost:8888")
    uvicorn.run(app, host="0.0.0.0", port=8888, log_level="info")


if __name__ == "__main__":
    main()
