"""
MOMOKA 记忆系统 — 日记忆 + 长期记忆的外部化 Markdown 存储。
参考: OpenClaw (memory/YYYY-MM-DD.md + MEMORY.md)
"""

import json
from pathlib import Path
from datetime import datetime


class MemoryStore:
    """文件系统记忆存储。"""

    def __init__(self, memory_dir: Path):
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        dreams_dir = self.memory_dir / ".dreams" / "long-term"
        dreams_dir.mkdir(parents=True, exist_ok=True)

    # -- 日记忆 ---
    def daily_path(self, date: datetime | None = None) -> Path:
        dt = date or datetime.now()
        return self.memory_dir / f"{dt.strftime('%Y-%m-%d')}.md"

    def write_daily(self, content: str, date: datetime | None = None):
        """追加写入日记忆。"""
        path = self.daily_path(date)
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"\n## {ts}\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
        return path

    def read_daily(self, days_back: int = 2) -> str:
        """加载近 N 天的日记忆。"""
        lines = []
        for i in range(days_back):
            import datetime as _dt
            dt = datetime.now() - _dt.timedelta(days=i)
            path = self.daily_path(dt)
            if path.exists():
                lines.append(f"\n### 记忆: {dt.strftime('%Y-%m-%d')}")
                lines.append(path.read_text(encoding="utf-8")[:2000])
        return "\n".join(lines)

    # -- 长期记忆 ---
    def long_term_path(self) -> Path:
        return self.memory_dir / "MEMORY.md"

    def write_long_term(self, content: str):
        """写入长期记忆。"""
        path = self.long_term_path()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## {ts}\n{content}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)

    def read_long_term(self) -> str:
        path = self.long_term_path()
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    # -- 判断记录 ---
    def record_judgment(self, output_id: str, score: int, context: str = ""):
        """记录用户的一次批注判断。"""
        record = {
            "output_id": output_id,
            "score": score,
            "context": context[:200],
            "timestamp": datetime.now().isoformat(),
        }
        path = self.memory_dir / ".dreams" / "short-term-recall.json"
        records = []
        if path.exists():
            try:
                records = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                records = []
        records.append(record)
        # 只保留最近 100 条
        records = records[-100:]
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    # -- 获取最近评分记录 ---
    def get_recent_judgments(self, count: int = 3) -> list[dict]:
        """读取最近 N 条评分记录。"""
        path = self.memory_dir / ".dreams" / "short-term-recall.json"
        if not path.exists():
            return []
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return records[-count:]

    # -- 上下文注入用 ---
    def get_injectable_context(self) -> str:
        """获取可注入 Agent 上下文的最相关记忆。"""
        parts = []
        recent = self.read_daily(2)
        if recent.strip():
            parts.append(recent)
        return "\n".join(parts)
