"""
MOMOKA HTTP API 服务器
提供会话管理、聊天、评分和静态文件服务。
"""

import json
import os
import asyncio
import uuid
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles
import uvicorn

from agents import Runner, trace

from file_agent import create_agent, skill_loader, memory_store
from momoka.config import LIKERT_LABELS, current_work_dir
from momoka.feedback import analyze_judgment, build_followup_prompt
from momoka.evolution import generate_evolution_proposals
from momoka.skill_loader import format_skill_prompt
from momoka.session_manager import SessionManager

PROJECT_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PROJECT_ROOT / "static"

# 全局会话管理器
session_manager = SessionManager(memory_store.memory_dir)


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
        if item.type == "tool_call_item":
            raw = item.raw_item
            if isinstance(raw, dict):
                name = raw.get("name", "unknown")
                args = raw.get("arguments", "{}")
            else:
                name = getattr(raw, "name", "unknown")
                args = getattr(raw, "arguments", "{}")
            current_call = {
                "tool": name,
                "args": args,
                "result": "",
            }
        elif item.type == "tool_call_output_item":
            output = item.output if hasattr(item, "output") else str(item.raw_item)
            if current_call:
                current_call["result"] = str(output)[:500]
                tool_calls.append(current_call)
                current_call = None
            else:
                tool_calls.append({
                    "tool": "unknown",
                    "args": "{}",
                    "result": str(output)[:500],
                })

    return tool_calls


# ── 会话管理 ──


async def api_create_session(request: Request) -> JSONResponse:
    """创建新会话。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "请求体必须是 JSON"}, status_code=400)

    goal = body.get("goal", "").strip()
    folder_path = body.get("folder_path", "").strip()

    if not goal:
        return JSONResponse({"error": "会话核心目标不能为空"}, status_code=400)
    if not folder_path:
        return JSONResponse({"error": "工作文件夹路径不能为空"}, status_code=400)

    folder = Path(folder_path)
    if not folder.exists():
        return JSONResponse({"error": f"文件夹不存在：{folder_path}"}, status_code=400)
    if not folder.is_dir():
        return JSONResponse({"error": f"路径不是文件夹：{folder_path}"}, status_code=400)

    session = session_manager.create_session(goal=goal, folder_path=str(folder.resolve()))
    return JSONResponse({"session": session})


async def api_list_sessions(_request: Request) -> JSONResponse:
    """列出所有会话。"""
    sessions = session_manager.list_sessions()
    return JSONResponse({"sessions": sessions})


async def api_get_session(request: Request) -> JSONResponse:
    """获取单个会话详情。"""
    session_id = request.path_params.get("session_id")
    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse({"error": f"未知会话：{session_id}"}, status_code=404)
    return JSONResponse({"session": session})


async def api_delete_session(request: Request) -> JSONResponse:
    """删除会话及其消息。"""
    session_id = request.path_params.get("session_id")
    if not session_manager.get_session(session_id):
        return JSONResponse({"error": f"未知会话：{session_id}"}, status_code=404)
    session_manager.delete_session(session_id)
    return JSONResponse({"success": True})


async def api_get_session_messages(request: Request) -> JSONResponse:
    """获取会话的消息历史。"""
    session_id = request.path_params.get("session_id")
    if not session_manager.get_session(session_id):
        return JSONResponse({"error": f"未知会话：{session_id}"}, status_code=404)
    messages = session_manager.get_messages(session_id)
    return JSONResponse({"messages": messages})


# ── 聊天 ──


async def api_chat(request: Request) -> JSONResponse:
    """处理聊天请求（支持会话绑定）。"""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "请求体必须是 JSON"}, status_code=400)

    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "消息不能为空"}, status_code=400)

    session_id = body.get("session_id", "").strip() or None
    output_id = body.get("output_id", "").strip() or f"out_{uuid.uuid4().hex[:12]}"
    topic = body.get("topic", "").strip() or message[:80]

    # 如果绑定会话，验证并设置工作目录
    work_dir = None
    if session_id:
        session = session_manager.get_session(session_id)
        if not session:
            return JSONResponse({"error": f"未知会话：{session_id}"}, status_code=404)
        work_dir = session.get("folder_path") or None
        if work_dir:
            current_work_dir.set(work_dir)

        # 保存用户消息
        session_manager.add_message(session_id, "user", message)

    feedback_boosts = memory_store.get_skill_feedback_boosts()
    matched = skill_loader.match_skills(message, topic=topic, feedback_boosts=feedback_boosts)
    matched_names = [m["meta"]["name"] for m in matched]
    skill_reasons = [
        {
            "name": m["meta"]["name"],
            "score": round(m.get("score", 0), 3),
            "reasons": m.get("reasons", []),
        }
        for m in matched
    ]

    # 创建 Agent（含技能匹配 + 记忆注入）
    agent = create_agent(
        message,
        topic=topic,
        matched_skills=matched,
        feedback_boosts=feedback_boosts,
        work_dir=work_dir,
    )

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

    memory_store.record_output(
        output_id=output_id,
        prompt=message,
        response=result.final_output,
        topic=topic,
        matched_skills=matched_names,
        tool_calls=tool_calls,
        session_id=session_id,
    )

    # 如果绑定会话，保存 Agent 回复
    if session_id:
        session_manager.add_message(
            session_id,
            "agent",
            result.final_output,
            output_id=output_id,
            matched_skills=matched_names,
            tool_calls=tool_calls,
        )

    return JSONResponse({
        "output_id": output_id,
        "topic": topic,
        "response": result.final_output,
        "tool_calls": tool_calls,
        "matched_skills": matched_names,
        "skill_reasons": skill_reasons,
        "session_id": session_id,
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
    comment = body.get("comment", "")
    should_continue = bool(body.get("continue", False))

    if not isinstance(score, int) or score < 1 or score > 7:
        return JSONResponse({
            "error": "评分必须是 1-7 的整数",
            "valid_range": {str(k): v for k, v in LIKERT_LABELS.items()},
        }, status_code=400)
    if not isinstance(context, str):
        return JSONResponse({"error": "批注上下文必须是字符串"}, status_code=400)
    if not isinstance(comment, str):
        return JSONResponse({"error": "文字批注必须是字符串"}, status_code=400)

    label = LIKERT_LABELS.get(score, "未知")
    output = memory_store.get_output(output_id)
    if output is None:
        return JSONResponse({
            "error": f"未知 output_id: {output_id}",
        }, status_code=404)

    # 记录判断到短期召回存储
    judgment = memory_store.record_judgment(output_id, score, context, comment)
    annotated_text = judgment.get("context", "")
    user_comment = judgment.get("comment", "")

    # 判断分析 (MOMOKA_PRD: Reflect 阶段)
    reflection = analyze_judgment(
        score=score,
        label=label,
        annotated_text=annotated_text,
        topic=judgment.get("topic", ""),
        user_comment=user_comment,
    )
    analysis = reflection["summary"]

    preference_update = memory_store.update_preferences(judgment, reflection)
    evolution_proposals = generate_evolution_proposals(skill_loader, memory_store, judgment)

    # 写入日记忆
    memory_store.write_daily(
        "\n".join([
            f"**评分**: {score}/7 ({label})",
            f"**分析**: {analysis}",
            f"**策略**: {reflection['next_guess_strategy']}",
            f"**上下文**: {annotated_text[:200]}",
            f"**文字批注**: {user_comment[:200] or '无'}",
        ])
    )

    payload = {
        "score": score,
        "label": label,
        "analysis": analysis,
        "reflection": reflection,
        "annotated_text": annotated_text[:2000],
        "comment": user_comment[:1000],
        "preference_update": preference_update,
        "evolution_proposals": evolution_proposals,
    }

    if should_continue:
        followup_prompt = build_followup_prompt(
            topic=judgment.get("topic", "") or output.get("topic", ""),
            output_text=output.get("response", ""),
            judgment={**judgment, "label": label},
            reflection=reflection,
        )
        next_output_id = f"out_{uuid.uuid4().hex[:12]}"
        followup_topic = judgment.get("topic", "") or output.get("topic", "")
        next_feedback_boosts = memory_store.get_skill_feedback_boosts()
        next_matched = skill_loader.match_skills(
            followup_prompt,
            topic=followup_topic,
            feedback_boosts=next_feedback_boosts,
        )
        next_skill_reasons = [
            {
                "name": m["meta"]["name"],
                "score": round(m.get("score", 0), 3),
                "reasons": m.get("reasons", []),
            }
            for m in next_matched
        ]
        # 尝试从原输出关联的会话中获取工作目录
        judge_work_dir = None
        output_session_id = output.get("session_id")
        if output_session_id:
            output_session = session_manager.get_session(output_session_id)
            if output_session:
                judge_work_dir = output_session.get("folder_path") or None
                if judge_work_dir:
                    current_work_dir.set(judge_work_dir)
        agent = create_agent(
            followup_prompt,
            topic=followup_topic,
            matched_skills=next_matched,
            feedback_boosts=next_feedback_boosts,
            work_dir=judge_work_dir,
        )
        try:
            with trace("MOMOKA Score-only Continuation"):
                result = await Runner.run(agent, followup_prompt)
        except Exception as e:
            return JSONResponse({
                **payload,
                "error": f"续猜失败: {e}",
            }, status_code=500)

        tool_calls = extract_tool_calls(result)
        memory_store.record_output(
            output_id=next_output_id,
            prompt=followup_prompt,
            response=result.final_output,
            topic=followup_topic,
            matched_skills=[m["meta"]["name"] for m in next_matched],
            tool_calls=tool_calls,
            session_id=output.get("session_id"),
        )
        memory_store.write_daily(
            f"**MOMOKA续猜**: {result.final_output[:300]}"
        )
        payload.update({
            "next_output_id": next_output_id,
            "next_response": result.final_output,
            "next_tool_calls": tool_calls,
            "next_skill_reasons": next_skill_reasons,
        })

    return JSONResponse(payload)


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


async def api_list_directories(request: Request) -> JSONResponse:
    """列出指定路径下的子目录（供前端目录选择器使用）。
    查询参数: path — 要列出的目录路径（空则返回根/驱动器列表）
    """
    path_str = request.query_params.get("path", "").strip()
    current = Path(path_str).resolve() if path_str else None

    # 如果没有指定路径，返回系统根目录（Windows 下返回驱动器列表）
    if current is None:
        if os.name == "nt":  # Windows
            try:
                drives_raw = os.listdrives()
            except AttributeError:
                # Python < 3.12 回退
                drives_raw = []
                for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    candidate = f"{letter}:\\"
                    if os.path.exists(candidate):
                        drives_raw.append(candidate)
            drives = []
            for d in drives_raw:
                name = d.rstrip("\\")
                drives.append({"name": name, "path": d, "is_dir": True})
            return JSONResponse({
                "path": "",
                "parent": None,
                "entries": drives,
            })
        else:
            return JSONResponse({
                "path": "",
                "parent": None,
                "entries": [{"name": "/", "path": "/", "is_dir": True}],
            })

    if not current.exists():
        return JSONResponse({"error": f"路径不存在：{current}"}, status_code=400)
    if not current.is_dir():
        return JSONResponse({"error": f"路径不是目录：{current}"}, status_code=400)

    try:
        entries = []
        for child in sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.is_dir():
                try:
                    entries.append({
                        "name": child.name,
                        "path": str(child.resolve()),
                        "is_dir": True,
                    })
                except (OSError, PermissionError):
                    pass  # 跳过无权限的目录

        parent = str(current.parent.resolve()) if current.parent != current else None

        return JSONResponse({
            "path": str(current.resolve()),
            "parent": parent,
            "entries": entries,
        })
    except PermissionError:
        return JSONResponse({"error": f"无权限访问：{current}"}, status_code=403)
    except OSError as e:
        return JSONResponse({"error": f"读取目录失败：{e}"}, status_code=500)


async def api_config(_request: Request) -> JSONResponse:
    """返回配置状态。"""
    return JSONResponse(check_config())


async def health(_request: Request) -> PlainTextResponse:
    return PlainTextResponse("MOMOKA OK")


# ── 静态文件 ──
STATIC_PATHS = [
    "index.html",
    "chat.html",
    "js/app.js",
    "js/session.js",
    "js/chat.js",
    "css/app.css",
    "css/syrretro.css",
    "css/mobile-framework.css",
    "css/themes/theme-a.css",
    "css/themes/theme-b.css",
    "css/themes/theme-c.css",
    "css/themes/theme-d.css",
    "css/themes/theme-e.css",
    "css/themes/aero.css",
    "css/themes/metro.css",
    "css/mobile/reset-base.css",
    "css/mobile/layout.css",
    "css/mobile/controls.css",
    "css/mobile/responsive.css",
    "css/mobile/accessibility.css",
    "css/ggmetro.css",
]

html_found = (STATIC_DIR / "index.html").exists()
print(f"[会话管理] Memory dir: {memory_store.memory_dir}")
print(f"[静态文件] index.html {'OK' if html_found else 'MISSING'} 存在")

# 路由
routes = [
    Route("/api/health", health),
    Route("/api/config", api_config),
    # 会话管理
    Route("/api/sessions", api_list_sessions),
    Route("/api/sessions", api_create_session, methods=["POST"]),
    Route("/api/sessions/{session_id}", api_get_session),
    Route("/api/sessions/{session_id}", api_delete_session, methods=["DELETE"]),
    Route("/api/sessions/{session_id}/messages", api_get_session_messages),
    # 聊天 & 判断
    Route("/api/chat", api_chat, methods=["POST"]),
    Route("/api/judge", api_judge, methods=["POST"]),
    Route("/api/skills", api_skills),
    Route("/api/memory", api_memory),
    Route("/api/directories", api_list_directories),
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
