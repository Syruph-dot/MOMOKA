"""
MOMOKA 文件助手 Agent
基于 OpenAI Agents SDK，配备文件系统工具与批注式判断交互协议。

核心特性 (MOMOKA_PRD):
  - 外部化 Markdown system prompt (prompts/AGENTS.md)
  - Skill 系统: 按需从 skills/ 加载 SKILL.md
  - 记忆系统: 日记忆 + 长期记忆 (memory/)
  - 批注式判断: Likert 7 点量表反馈
"""

import sys
import os
import uuid
from pathlib import Path

from momoka.config import load_local_env

load_local_env()

# 环境变量配置：优先 ALIYUN_API_KEY，回退 OPENAI_API_KEY，默认使用 DashScope
if os.environ.get("ALIYUN_API_KEY"):
    os.environ.setdefault("OPENAI_API_KEY", os.environ["ALIYUN_API_KEY"])
os.environ.setdefault("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
os.environ.setdefault("MOMOKA_MODEL", "qwen-plus")
os.environ.setdefault("OPENAI_DEFAULT_MODEL", os.environ["MOMOKA_MODEL"])

from agents import Agent, Runner, trace

from tools.time_tool import get_current_time
from tools.file_reader import read_file
from tools.file_writer import write_file
from tools.file_lister import list_files
from tools.file_appender import append_file

from momoka.config import PROMPTS_DIR, SKILLS_DIR, MEMORY_DIR, LIKERT_LABELS, current_work_dir
from momoka.skill_loader import SkillLoader, format_skill_prompt
from momoka.memory import MemoryStore

# 全局实例
skill_loader = SkillLoader(SKILLS_DIR)
memory_store = MemoryStore(MEMORY_DIR)


def build_system_prompt(
    user_message: str = "",
    topic: str = "",
    matched_skills: list[dict] | None = None,
    feedback_boosts: dict[str, float] | None = None,
    work_dir: str | None = None,
) -> str:
    """构建完整的 system prompt = 基础 prompt + 匹配技能 + 相关记忆。"""
    parts = []

    # 1. 基础 prompt (从 AGENTS.md 加载)
    prompt_path = PROMPTS_DIR / "AGENTS.md"
    if prompt_path.exists():
        parts.append(prompt_path.read_text(encoding="utf-8"))
    else:
        parts.append("你是 MOMOKA 文件助手 Agent。")

    # 1.5 当前工作目录（注入让 Agent 知道自己被限制在此目录下）
    if work_dir:
        parts.append(
            f"\n## 当前工作目录\n"
            f"你被限制在以下目录中操作：{work_dir}\n"
            f"文件操作请使用相对于此目录的路径，不要使用绝对路径。\n"
        )

    # 2. 匹配的技能 (Memento-Skills 范式: Read 阶段)
    if user_message:
        matched = matched_skills
        if matched is None:
            matched = skill_loader.match_skills(
                user_message,
                topic=topic,
                feedback_boosts=feedback_boosts,
            )
        if matched:
            skills_text = format_skill_prompt(matched)
            parts.append(skills_text)

    # 3. 最近记忆 (OpenClaw 范式: 上下文注入)
    memory_context = memory_store.get_injectable_context()
    if memory_context.strip():
        parts.append(f"\n## 最近记忆\n{memory_context}")

    preference_context = memory_store.get_preference_context()
    if preference_context.strip():
        parts.append(preference_context)

    # 4. 用户最近反馈（批注判断闭环）
    recent = memory_store.get_recent_judgments(3)
    if recent:
        feedback_lines = ["\n## 用户最近反馈"]
        for r in recent:
            text = r.get("context", "")
            score = r.get("score", 0)
            feeling = LIKERT_LABELS.get(score, "未知")
            comment = (r.get("comment") or "").strip()
            comment_line = f"\n<UserComment>{comment}</UserComment>" if comment else ""
            feedback_lines.append(
                f"\n<AnnotateText>{{{text}}}</AnnotateText>"
                f"\n<UserScore>score:{score}, feeling:{feeling}</UserScore>"
                f"{comment_line}"
            )
        parts.append("\n".join(feedback_lines))

    return "\n".join(parts)


def create_agent(
    user_message: str = "",
    topic: str = "",
    matched_skills: list[dict] | None = None,
    feedback_boosts: dict[str, float] | None = None,
    work_dir: str | None = None,
) -> Agent:
    """创建 MOMOKA Agent 实例，注入技能和记忆。"""
    return Agent(
        name="MOMOKA",
        instructions=build_system_prompt(
            user_message,
            topic=topic,
            matched_skills=matched_skills,
            feedback_boosts=feedback_boosts,
            work_dir=work_dir,
        ),
        model=os.environ["MOMOKA_MODEL"],
        tools=[
            get_current_time,
            read_file,
            write_file,
            list_files,
            append_file,
        ],
    )


def log_tool_calls(result):
    """打印工具调用日志。"""
    if not hasattr(result, "new_items"):
        return
    for item in result.new_items:
        if item.type == "tool_call_item":
            raw = item.raw_item
            if isinstance(raw, dict):
                name = raw.get("name", "?")
                args = raw.get("arguments", "{}")
            else:
                name = getattr(raw, "name", "?")
                args = getattr(raw, "arguments", "{}")
            print(f"\n  [TOOL] {name}({args})")
        elif item.type == "tool_call_output_item":
            output = item.output if hasattr(item, "output") else str(item.raw_item)
            preview = str(output)[:200]
            print(f"  [RESULT] {preview}")


def run_cli():
    """命令行交互模式。"""
    # CLI 模式下将当前目录设为会话工作目录（限制文件操作范围）
    cli_work_dir = str(Path.cwd().resolve())
    current_work_dir.set(cli_work_dir)

    print("MOMOKA 文件助手已就绪 (输入 /quit 退出)")
    print(f"  已加载 {len(skill_loader.list_skills())} 个技能")
    print(f"  工作目录: {cli_work_dir}")
    print("-" * 50)

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit"):
            print("再见。")
            break

        agent = create_agent(user_input, work_dir=cli_work_dir)

        with trace("MOMOKA Agent"):
            result = Runner.run_sync(agent, user_input)

        log_tool_calls(result)
        print(f"\n{result.final_output}")

        # 记录到日记忆
        memory_store.write_daily(
            f"**用户**: {user_input}\n**Agent**: {result.final_output[:300]}"
        )


if __name__ == "__main__":
    run_cli()
