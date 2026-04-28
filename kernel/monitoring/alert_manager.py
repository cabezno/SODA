from __future__ import annotations


class AlertManager:
    """Computes simple preventive alerts from usage and cost telemetry."""

    COST_WARN_USD = 5.0
    COST_CRITICAL_USD = 20.0
    LATENCY_WARN_MS = 30_000
    ERROR_RATE_WARN = 0.30
    MIN_CALLS_FOR_ERROR_ALERT = 3

    # Gemini free tier: 1500 requests/day (warn at 80%, critical at 90%)
    GEMINI_FREE_DAILY_LIMIT = 1500
    GEMINI_FREE_WARN_PCT = 0.80
    GEMINI_FREE_CRITICAL_PCT = 0.90

    # Claude budget guard: warn when per-session cost exceeds these thresholds
    CLAUDE_BUDGET_WARN_USD = 3.0
    CLAUDE_BUDGET_CRITICAL_USD = 10.0

    # Context size: warn when token count reaches 70% of model limit
    CONTEXT_TOKEN_LIMITS = {
        "claude": 100_000,
        "gemini": 1_000_000,
        "ollama": 32_000,
    }
    CONTEXT_WARN_PCT = 0.70

    def __init__(self, usage_monitor):
        self.usage_monitor = usage_monitor

    def evaluate(self) -> list[dict]:
        summary = self.usage_monitor.summary()
        grouped = self.usage_monitor.grouped_summary()
        alerts: list[dict] = []

        # --- Total cost alerts ---
        cost = summary.get("cost_usd", 0.0)
        if cost >= self.COST_CRITICAL_USD:
            alerts.append({
                "level": "critical",
                "kind": "cost",
                "message": "El costo acumulado superó el umbral crítico.",
                "data": {"cost_usd": cost},
            })
        elif cost >= self.COST_WARN_USD:
            alerts.append({
                "level": "warning",
                "kind": "cost",
                "message": "El costo acumulado superó el umbral preventivo.",
                "data": {"cost_usd": cost},
            })

        # --- Latency alert ---
        if summary.get("avg_latency_ms", 0) >= self.LATENCY_WARN_MS:
            alerts.append({
                "level": "warning",
                "kind": "latency",
                "message": "La latencia promedio está por encima del umbral técnico.",
                "data": {"avg_latency_ms": summary.get("avg_latency_ms", 0)},
            })

        # --- Per-provider alerts ---
        gemini_calls = 0
        for item in grouped:
            total_calls = max(0, int(item.get("total_calls", 0)))
            error_calls = max(0, int(item.get("error_calls", 0)))
            provider = (item.get("provider") or "").lower()
            provider_cost = float(item.get("cost_usd", 0.0))

            # Error rate alert
            if total_calls >= self.MIN_CALLS_FOR_ERROR_ALERT:
                error_rate = error_calls / total_calls
                if error_rate >= self.ERROR_RATE_WARN:
                    alerts.append({
                        "level": "warning",
                        "kind": "error_rate",
                        "message": "Un modelo presenta una tasa de error elevada.",
                        "data": {
                            "provider": item.get("provider"),
                            "model": item.get("model"),
                            "error_rate": error_rate,
                            "total_calls": total_calls,
                            "error_calls": error_calls,
                        },
                    })

            # Gemini free tier usage alert
            if "gemini" in provider:
                gemini_calls += total_calls

            # Claude per-session budget alert
            if "claude" in provider:
                if provider_cost >= self.CLAUDE_BUDGET_CRITICAL_USD:
                    alerts.append({
                        "level": "critical",
                        "kind": "claude_budget",
                        "message": "El costo de Claude superó el umbral crítico de sesión.",
                        "data": {"provider": item.get("provider"), "cost_usd": provider_cost},
                    })
                elif provider_cost >= self.CLAUDE_BUDGET_WARN_USD:
                    alerts.append({
                        "level": "warning",
                        "kind": "claude_budget",
                        "message": "El costo de Claude se acerca al umbral de sesión.",
                        "data": {"provider": item.get("provider"), "cost_usd": provider_cost},
                    })

            # Context size alert (tokens_input vs model limit)
            tokens_in = int(item.get("tokens_input", 0) or 0)
            for prov_key, limit in self.CONTEXT_TOKEN_LIMITS.items():
                if prov_key in provider and tokens_in >= int(limit * self.CONTEXT_WARN_PCT):
                    alerts.append({
                        "level": "warning",
                        "kind": "context_size",
                        "message": f"El contexto de {item.get('provider')} se acerca al límite del modelo ({tokens_in:,} tokens).",
                        "data": {
                            "provider": item.get("provider"),
                            "tokens_input": tokens_in,
                            "limit": limit,
                            "pct": round(tokens_in / limit, 3),
                        },
                    })

        # Gemini free tier aggregate
        if gemini_calls >= int(self.GEMINI_FREE_DAILY_LIMIT * self.GEMINI_FREE_CRITICAL_PCT):
            alerts.append({
                "level": "critical",
                "kind": "gemini_quota",
                "message": f"CRÍTICO: Se usaron {gemini_calls} llamadas Gemini hoy — cuota casi agotada (límite: {self.GEMINI_FREE_DAILY_LIMIT}/día).",
                "data": {
                    "gemini_calls_today": gemini_calls,
                    "daily_limit": self.GEMINI_FREE_DAILY_LIMIT,
                    "pct": round(gemini_calls / self.GEMINI_FREE_DAILY_LIMIT, 3),
                },
            })
        elif gemini_calls >= int(self.GEMINI_FREE_DAILY_LIMIT * self.GEMINI_FREE_WARN_PCT):
            alerts.append({
                "level": "warning",
                "kind": "gemini_quota",
                "message": f"Se usaron {gemini_calls} llamadas Gemini hoy (límite free: {self.GEMINI_FREE_DAILY_LIMIT}/día).",
                "data": {
                    "gemini_calls_today": gemini_calls,
                    "daily_limit": self.GEMINI_FREE_DAILY_LIMIT,
                    "pct": round(gemini_calls / self.GEMINI_FREE_DAILY_LIMIT, 3),
                },
            })

        return alerts