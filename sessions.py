from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


SessionStatus = Literal["idle", "running", "waiting_confirmation", "stopped", "error"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SessionRecord:
    id: str
    name: str
    project_dir: str
    created_at: str
    updated_at: str
    status: SessionStatus = "idle"
    messages: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(cls, *, name: str, project_dir: Path) -> "SessionRecord":
        now = utc_now()
        return cls(
            id=uuid.uuid4().hex,
            name=name.strip() or project_dir.name,
            project_dir=str(project_dir.resolve()),
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionRecord":
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or "Untitled"),
            project_dir=str(data["project_dir"]),
            created_at=str(data.get("created_at") or utc_now()),
            updated_at=str(data.get("updated_at") or utc_now()),
            status=data.get("status", "idle"),
            messages=list(data.get("messages") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "project_dir": self.project_dir,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "messages": self.messages,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "project_dir": self.project_dir,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "message_count": len(self.messages),
        }


class SessionStore:
    """JSON-backed local session storage."""

    def __init__(self, root: Path | None = None):
        self.root = (root or Path.home() / ".agent_v2" / "sessions").expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def list(self) -> list[SessionRecord]:
        records: list[SessionRecord] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                records.append(self._read(path))
            except (json.JSONDecodeError, KeyError, OSError, TypeError, ValueError):
                continue
        return sorted(records, key=lambda s: s.updated_at, reverse=True)

    def create(self, *, name: str, project_dir: str) -> SessionRecord:
        path = validate_project_dir(project_dir)
        record = SessionRecord.create(name=name, project_dir=path)
        self.save(record)
        return record

    def get(self, session_id: str) -> SessionRecord:
        path = self._path(session_id)
        if not path.exists():
            raise KeyError(session_id)
        return self._read(path)

    def save(self, record: SessionRecord) -> None:
        record.updated_at = utc_now()
        tmp_path = self._path(record.id).with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._path(record.id))

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        if not path.exists():
            raise KeyError(session_id)
        path.unlink()

    def append_message(self, session_id: str, message: dict[str, Any]) -> SessionRecord:
        record = self.get(session_id)
        record.messages.append(message)
        self.save(record)
        return record

    def set_status(self, session_id: str, status: SessionStatus) -> SessionRecord:
        record = self.get(session_id)
        record.status = status
        self.save(record)
        return record

    def _path(self, session_id: str) -> Path:
        clean = "".join(ch for ch in session_id if ch.isalnum() or ch in ("-", "_"))
        if clean != session_id or not clean:
            raise KeyError(session_id)
        return self.root / f"{clean}.json"

    def _read(self, path: Path) -> SessionRecord:
        return SessionRecord.from_dict(json.loads(path.read_text(encoding="utf-8-sig")))


def validate_project_dir(project_dir: str, *, base_dir: Path | None = None) -> Path:
    if not project_dir.strip():
        raise ValueError("项目目录不能为空。")
    raw_path = Path(project_dir).expanduser()
    if not raw_path.is_absolute() and base_dir is not None:
        raw_path = base_dir / raw_path
    path = raw_path.resolve()
    if not path.exists():
        raise ValueError(f"项目目录不存在：{path}")
    if not path.is_dir():
        raise ValueError(f"项目路径不是目录：{path}")
    return path
