from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m: float
    output_per_1m: float


class CostTracker:
    # Standard Google Cloud Vertex AI prices (USD per 1M tokens)
    PRICES = {
        "gemini": {
            "gemini-3.1-pro-preview": ModelPrice(input_per_1m=1.25, output_per_1m=10.0),
            "gemini-3-flash-preview": ModelPrice(input_per_1m=0.15, output_per_1m=0.60),
            "gemini-3.1-flash-lite-preview": ModelPrice(input_per_1m=0.075, output_per_1m=0.30),
            "gemini-2.5-pro": ModelPrice(input_per_1m=1.25, output_per_1m=3.75),
            "gemini-2.5-flash": ModelPrice(input_per_1m=0.10, output_per_1m=0.30),
        },
        "gemini_pro": {
            "gemini-3.1-pro-preview": ModelPrice(input_per_1m=1.25, output_per_1m=10.0),
            "gemini-2.5-pro": ModelPrice(input_per_1m=1.25, output_per_1m=3.75),
        },
        "claude": {
            "claude-3-5-sonnet-20241022": ModelPrice(input_per_1m=3.0, output_per_1m=15.0),
            "claude-3-haiku-20240307": ModelPrice(input_per_1m=0.25, output_per_1m=1.25),
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
