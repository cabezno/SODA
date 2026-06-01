from __future__ import annotations

from typing import Optional

from kernel.drivers.generic_openai_driver import GenericOpenAIDriver

# Known providers: auto base_url + driver type
KNOWN_PROVIDERS: dict[str, dict] = {
    # ── OpenAI-compatible third-party providers ─────────────────────────────
    "groq":        {"base_url": "https://api.groq.com/openai/v1",          "type": "openai_compat", "default_model": "llama-3.3-70b-versatile",                          "display_name": "Groq (Llama ultra-rápido)"},
    "mistral":     {"base_url": "https://api.mistral.ai/v1",                "type": "openai_compat", "default_model": "mistral-large-latest",                              "display_name": "Mistral AI"},
    "together":    {"base_url": "https://api.together.xyz/v1",              "type": "openai_compat", "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",     "display_name": "Together AI"},
    "deepseek":    {"base_url": "https://api.deepseek.com/v1",              "type": "openai_compat", "default_model": "deepseek-reasoner",                                 "display_name": "DeepSeek (R1/V4)"},
    "perplexity":  {"base_url": "https://api.perplexity.ai",                "type": "openai_compat", "default_model": "llama-3.1-sonar-large-128k-online",                "display_name": "Perplexity (búsqueda web)"},
    "fireworks":   {"base_url": "https://api.fireworks.ai/inference/v1",    "type": "openai_compat", "default_model": "accounts/fireworks/models/firefunction-v2",        "display_name": "Fireworks AI"},
    "openrouter":  {"base_url": "https://openrouter.ai/api/v1",             "type": "openai_compat", "default_model": "anthropic/gemini-3-haiku",                         "display_name": "OpenRouter (multi-proveedor)"},
    "cerebras":    {"base_url": "https://api.cerebras.ai/v1",               "type": "openai_compat", "default_model": "llama3.1-70b",                                     "display_name": "Cerebras"},
    "novita":      {"base_url": "https://api.novita.ai/v3/openai",          "type": "openai_compat", "default_model": "meta-llama/llama-3.1-70b-instruct",                "display_name": "Novita AI"},
    "xai":         {"base_url": "https://api.x.ai/v1",                      "type": "openai_compat", "default_model": "grok-beta",                                        "display_name": "xAI Grok"},
    "cohere":      {"base_url": "https://api.cohere.com/compatibility/v1",  "type": "openai_compat", "default_model": "command-r-plus",                                   "display_name": "Cohere"},
    "lepton":      {"base_url": "https://llama3-1-70b.lepton.run/api/v1",   "type": "openai_compat", "default_model": "llama3-1-70b",                                     "display_name": "Lepton AI"},
    "anyscale":    {"base_url": "https://api.endpoints.anyscale.com/v1",    "type": "openai_compat", "default_model": "meta-llama/Meta-Llama-3-70B-Instruct",             "display_name": "Anyscale"},
    "nvidia":      {"base_url": "https://integrate.api.nvidia.com/v1",      "type": "openai_compat", "default_model": "meta/llama-3.1-70b-instruct",                      "display_name": "NVIDIA NIM"},
    "sambanova":   {"base_url": "https://api.sambanova.ai/v1",              "type": "openai_compat", "default_model": "Meta-Llama-3.1-70B-Instruct",                      "display_name": "SambaNova"},
    "hyperbolic":  {"base_url": "https://api.hyperbolic.xyz/v1",            "type": "openai_compat", "default_model": "meta-llama/Meta-Llama-3.1-70B-Instruct",           "display_name": "Hyperbolic"},
}


def detect_driver_type(name: str, base_url: Optional[str] = None) -> str:
    """Infer driver type from provider name or base URL."""
    n = name.lower()
    if n in KNOWN_PROVIDERS:
        return KNOWN_PROVIDERS[n]["type"]
    if base_url:
        url = base_url.lower()
        if "chat/completions" in url or "openai" in url or "openrouter" in url:
            return "openai_compat"
    # Fallback: assume OpenAI-compatible (most common)
    return "openai_compat"


def get_default_base_url(name: str) -> str:
    """Return the default base URL for a known provider, empty string otherwise."""
    return KNOWN_PROVIDERS.get(name.lower(), {}).get("base_url", "")


def get_default_model(name: str) -> str:
    """Return a reasonable default model for a known provider."""
    return KNOWN_PROVIDERS.get(name.lower(), {}).get("default_model", "")


def build_driver(
    name: str,
    api_key: str,
    model: str,
    base_url: Optional[str] = None,
    driver_type: Optional[str] = None,
) -> GenericOpenAIDriver:
    """Create the right driver instance for a custom provider."""
    resolved_type = driver_type or detect_driver_type(name, base_url)
    resolved_url = base_url or get_default_base_url(name)
    resolved_model = model or get_default_model(name) or "gpt-4o"

    if resolved_type == "openai_compat":
        if not resolved_url:
            resolved_url = "https://api.openai.com/v1"
        return GenericOpenAIDriver(
            provider_name=name,
            api_key=api_key,
            base_url=resolved_url,
            model_name=resolved_model,
        )

    # Fallback to generic OpenAI-compat for unknown types
    return GenericOpenAIDriver(
        provider_name=name,
        api_key=api_key,
        base_url=resolved_url or "https://api.openai.com/v1",
        model_name=resolved_model,
    )
