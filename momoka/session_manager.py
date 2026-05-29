"""
MOMOKA 会话管理器 — 会话级管理与消息持久化。
"""

import json
import uuid
import shutil
from pathlib import Path
from datetime import datetime


class SessionManager:
    """管理会话及其消息。"""

    def __init__(self, memory_dir: Path):
        self.sessions_dir = memory_dir / ".sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_file = self.sessions_dir / "sessions.json"

    # ── 会话 CRUD ──

    def _read_sessions(self) -> list[dict]:
        if not self._sessions_file.exists():
            return []
        try:
            return json.loads(self._sessions_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_sessions(self, sessions: list[dict]):
        self._sessions_file.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def create_session(self, goal: str, folder_path: str, session_id: str | None = None) -> dict:
        """创建新会话。"""
        sid = session_id or f"ses_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        # 从 goal 自动截取会话名称
        name = goal.strip()[:50]
        if len(goal) > 50:
            name += "…"

        session = {
            "id": sid,
            "name": name,
            "goal": goal,
            "folder_path": folder_path,
            "created_at": now,
            "message_count": 0,
            "last_message_at": now,
        }

        sessions = self._read_sessions()
        sessions.insert(0, session)
        self._write_sessions(sessions)

        # 初始化消息存储
        self._messages_path(sid).parent.mkdir(parents=True, exist_ok=True)
        self._write_messages(sid, [])

        return session

    def list_sessions(self) -> list[dict]:
        return self._read_sessions()

    def get_session(self, session_id: str) -> dict | None:
        for s in self._read_sessions():
            if s["id"] == session_id:
                return s
        return None

    def update_session(self, session_id: str, updates: dict) -> dict | None:
        """更新会话字段（如 message_count, last_message_at 等）。"""
        sessions = self._read_sessions()
        for s in sessions:
            if s["id"] == session_id:
                s.update(updates)
                self._write_sessions(sessions)
                return s
        return None

    def delete_session(self, session_id: str) -> bool:
        sessions = self._read_sessions()
        filtered = [s for s in sessions if s["id"] != session_id]
        if len(filtered) == len(sessions):
            return False
        self._write_sessions(filtered)

        msg_dir = self._messages_path(session_id).parent
        if msg_dir.exists():
            shutil.rmtree(str(msg_dir))
        return True

    # ── 消息持久化 ──

    def _messages_path(self, session_id: str) -> Path:
        return self.sessions_dir / session_id / "messages.json"

    def _read_messages(self, session_id: str) -> list[dict]:
        path = self._messages_path(session_id)
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_messages(self, session_id: str, messages: list[dict]):
        path = self._messages_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    def add_message(self, session_id: str, role: str, content: str, **extra) -> dict:
        """向会话添加一条消息并返回。"""
        messages = self._read_messages(session_id)
        msg = {
            "id": f"msg_{uuid.uuid4().hex[:12]}",
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **extra,
        }
        messages.append(msg)
        self._write_messages(session_id, messages)

        # 更新会话元信息
        count = len(messages)
        self.update_session(session_id, {
            "message_count": count,
            "last_message_at": msg["timestamp"],
        })

        return msg

    def get_messages(self, session_id: str, limit: int = 200) -> list[dict]:
        """获取会话消息历史。"""
        messages = self._read_messages(session_id)
        return messages if limit is None else messages[-limit:]
