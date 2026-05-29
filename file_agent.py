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

from momoka.config import PROMPTS_DIR, SKILLS_DIR, MEMORY_DIR
from momoka.skill_loader import SkillLoader, format_skill_prompt
from momoka.memory import MemoryStore

# 全局实例
skill_loader = SkillLoader(SKILLS_DIR)
memory_store = MemoryStore(MEMORY_DIR)


def build_system_prompt(user_message: str = "") -> str:
    """构建完整的 system prompt = 基础 prompt + 匹配技能 + 相关记忆。"""
    parts = []

    # 1. 基础 prompt (从 AGENTS.md 加载)
    prompt_path = PROMPTS_DIR / "AGENTS.md"
    if prompt_path.exists():
        parts.append(prompt_path.read_text(encoding="utf-8"))
    else:
        parts.append("你是 MOMOKA 文件助手 Agent。")

    # 2. 匹配的技能 (Memento-Skills 范式: Read 阶段)
    if user_message:
        matched = skill_loader.match_skills(user_message)
        if matched:
            skills_text = format_skill_prompt(matched)
            parts.append(skills_text)

    # 3. 最近记忆 (OpenClaw 范式: 上下文注入)
    memory_context = memory_store.get_injectable_context()
    if memory_context.strip():
        parts.append(f"\n## 最近记忆\n{memory_context}")

    return "\n".join(parts)


def create_agent(user_message: str = "") -> Agent:
    """创建 MOMOKA Agent 实例，注入技能和记忆。"""
    return Agent(
        name="MOMOKA",
        instructions=build_system_prompt(user_message),
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
        if hasattr(item, "raw_item"):
            raw = item.raw_item
            if hasattr(raw, "type") and raw.type == "function_call":
                name = getattr(raw, "name", "?")
                args = getattr(raw, "arguments", "{}")
                print(f"\n  [TOOL] {name}({args})")
            elif hasattr(raw, "type") and raw.type == "function_call_output":
                output = getattr(raw, "output", "")
                preview = str(output)[:200]
                print(f"  [RESULT] {preview}")


def run_cli():
    """命令行交互模式。"""
    print("MOMOKA 文件助手已就绪 (输入 /quit 退出)")
    print(f"  已加载 {len(skill_loader.list_skills())} 个技能")
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

        agent = create_agent(user_input)

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
