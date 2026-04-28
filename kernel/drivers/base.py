from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Optional

from kernel.monitoring.cost_tracker import CostTracker
from kernel.monitoring.usage_monitor import UsageMonitor


@dataclass
class DriverResponse:
    content: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    model_used: str
    cost_usd: float
    error_code: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseDriver(ABC):
    provider: str = "unknown"

    def __init__(self, model_name: str):
        self.model = model_name
        base_dir = Path(__file__).resolve().parent.parent.parent
        db_path = base_dir / "data" / "usage_metrics.db"
        self.usage_monitor = UsageMonitor(db_path)
        self.cost_tracker = CostTracker(self.usage_monitor)

    @abstractmethod
    async def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: str = "text",
        images: Optional[list] = None,
        metadata: Optional[dict] = None,
    ) -> DriverResponse:
        raise NotImplementedError

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Heuristic used in the project health monitor as well.
        return max(1, len(text or "") // 4)

    @staticmethod
    def _extract_error_code(content: str) -> Optional[str]:
        if not content or not content.startswith("ERROR:"):
            return None
        parts = content.split(":", 2)
        return parts[1] if len(parts) > 1 else "UNKNOWN"

    def _build_response(
        self,
        *,
        content: str,
        system_prompt: str,
        user_message: str,
        latency_start: float,
        model_used: Optional[str] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> DriverResponse:
        in_tokens = tokens_input if tokens_input is not None else self._estimate_tokens(system_prompt + "\n" + user_message)
        out_tokens = tokens_output if tokens_output is not None else self._estimate_tokens(content)
        latency_ms = int((perf_counter() - latency_start) * 1000)
        model = model_used or self.model
        error_code = self._extract_error_code(content)
        cost_usd = self.cost_tracker.estimate_cost(self.provider, model, in_tokens, out_tokens)

        self.usage_monitor.record(
            provider=self.provider,
            model=model,
            tokens_input=in_tokens,
            tokens_output=out_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            error_code=error_code,
            metadata=metadata or {},
        )

        return DriverResponse(
            content=content,
            tokens_input=in_tokens,
            tokens_output=out_tokens,
            latency_ms=latency_ms,
            model_used=model,
            cost_usd=cost_usd,
            error_code=error_code,
            metadata=metadata or {},
        )
