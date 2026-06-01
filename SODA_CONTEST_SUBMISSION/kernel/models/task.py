from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Task:
    id: str
    role: str
    provider: str
    input: str
    project_id: Optional[str] = None
    module: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TaskResult:
    task_id: str
    output: str
    success: bool
    latency_s: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    error: Optional[str] = None
    finished_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)
