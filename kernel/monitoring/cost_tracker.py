from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m: float
    output_per_1m: float


class CostTracker:
    # Conservative references. Local models are always 0.
    PRICES = {
        "claude": {
            "claude-sonnet-4-6": ModelPrice(input_per_1m=3.0, output_per_1m=15.0),
            "claude-sonnet-4-5-20250929": ModelPrice(input_per_1m=3.0, output_per_1m=15.0),
            "claude-haiku-4-5": ModelPrice(input_per_1m=0.8, output_per_1m=4.0),
        },
        "gemini": {
            # SODA prioriza free tier en Gemini; keep near-zero unless billed usage is configured.
            "gemini-2.5-pro": ModelPrice(input_per_1m=0.0, output_per_1m=0.0),
            "gemini-2.5-flash": ModelPrice(input_per_1m=0.0, output_per_1m=0.0),
            "gemini-3.0-pro": ModelPrice(input_per_1m=0.0, output_per_1m=0.0),
            "gemini-3.0-flash": ModelPrice(input_per_1m=0.0, output_per_1m=0.0),
            "gemini-2.0-pro": ModelPrice(input_per_1m=0.0, output_per_1m=0.0),
            "gemini-2.0-flash": ModelPrice(input_per_1m=0.0, output_per_1m=0.0),
        },
        "ollama": {},
    }

    def __init__(self, usage_monitor):
        self.usage_monitor = usage_monitor

    def estimate_cost(self, provider: str, model: str, tokens_input: int, tokens_output: int) -> float:
        if provider == "ollama":
            return 0.0
        price = self.PRICES.get(provider, {}).get(model)
        if not price:
            return 0.0
        return (
            (max(0, tokens_input) / 1_000_000.0) * price.input_per_1m
            + (max(0, tokens_output) / 1_000_000.0) * price.output_per_1m
        )
