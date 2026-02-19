from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Checkpoint:
    started_at: str
    updated_at: str
    status: str = "running"
    exit_code: int | None = None
    completed_phases: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "exit_code": self.exit_code,
            "completed_phases": list(self.completed_phases),
            "context": dict(self.context),
            "retries": dict(self.retries),
            "errors": list(self.errors),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Checkpoint":
        started_at = str(payload.get("started_at") or utc_now_iso())
        updated_at = str(payload.get("updated_at") or started_at)
        status = str(payload.get("status") or "running")
        exit_code = payload.get("exit_code")
        completed_phases = [str(x) for x in payload.get("completed_phases") or []]
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        retries = payload.get("retries") if isinstance(payload.get("retries"), dict) else {}
        errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
        return cls(
            started_at=started_at,
            updated_at=updated_at,
            status=status,
            exit_code=int(exit_code) if isinstance(exit_code, int) else None,
            completed_phases=completed_phases,
            context=context,
            retries={str(k): int(v) for k, v in retries.items() if isinstance(v, int)},
            errors=errors,
        )


class CheckpointManager:
    def __init__(self, path: Path, checkpoint: Checkpoint):
        self.path = path
        self.checkpoint = checkpoint

    @classmethod
    def create_or_resume(cls, path: Path, resume: bool) -> "CheckpointManager":
        if resume:
            if not path.exists():
                raise FileNotFoundError(f"Checkpoint not found: {path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            checkpoint = Checkpoint.from_dict(payload)
            return cls(path, checkpoint)

        checkpoint = Checkpoint(started_at=utc_now_iso(), updated_at=utc_now_iso())
        manager = cls(path, checkpoint)
        manager.write()
        return manager

    def is_phase_complete(self, phase: str) -> bool:
        return phase in self.checkpoint.completed_phases

    def mark_phase_complete(self, phase: str, data: dict[str, Any] | None = None) -> None:
        if phase not in self.checkpoint.completed_phases:
            self.checkpoint.completed_phases.append(phase)
        if data:
            self.checkpoint.context.update(data)
        self.checkpoint.updated_at = utc_now_iso()
        self.write()

    def set_context(self, key: str, value: Any) -> None:
        self.checkpoint.context[key] = value
        self.checkpoint.updated_at = utc_now_iso()
        self.write()

    def increment_retry(self, key: str) -> int:
        next_count = int(self.checkpoint.retries.get(key) or 0) + 1
        self.checkpoint.retries[key] = next_count
        self.checkpoint.updated_at = utc_now_iso()
        self.write()
        return next_count

    def add_error(self, phase: str, message: str) -> None:
        self.checkpoint.errors.append(
            {
                "time": utc_now_iso(),
                "phase": phase,
                "message": message,
            }
        )
        self.checkpoint.updated_at = utc_now_iso()
        self.write()

    def finalize(self, status: str, exit_code: int) -> None:
        self.checkpoint.status = status
        self.checkpoint.exit_code = exit_code
        self.checkpoint.updated_at = utc_now_iso()
        self.write()

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.checkpoint.to_dict(), indent=2), encoding="utf-8")
