"""
UIDesignAgent — generates a design_spec.json between ARCH and DEV phases.

Analyzes the project blueprint and architecture to produce a complete visual
design specification: color palette, typography, spacing, component inventory,
layout patterns, and design system choice.

The spec is saved to the project workspace and later consumed by
DesignContextInjector to enrich frontend module generation prompts.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DesignSpec:
    design_system: str                     # tailwind | shadcn | mui | chakra | daisyui | vanilla
    color_palette: dict                    # {primary, secondary, success, warning, danger, neutral}
    typography: dict                       # {font_sans, font_mono, scale, heading_weight}
    spacing_base: int                      # 8 (standard 8px grid)
    border_radius: dict                    # {sm, md, lg, full}
    shadows: dict                          # {sm, md, lg}
    dark_mode: bool
    layout_pattern: str                    # dashboard | landing | app_shell | minimal
    component_inventory: list[str]         # ["navbar", "sidebar", "data_table", "card_grid", ...]
    css_variables: str                     # complete :root CSS block
    rationale: str                         # why these choices were made
    mock_data: dict = field(default_factory=dict)           # domain-specific seed data for UI realism
    component_specs: list = field(default_factory=list)     # [{name, description, visual, tailwind_classes, interactions}]
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "design_system": self.design_system,
            "color_palette": self.color_palette,
            "typography": self.typography,
            "spacing_base": self.spacing_base,
            "border_radius": self.border_radius,
            "shadows": self.shadows,
            "dark_mode": self.dark_mode,
            "layout_pattern": self.layout_pattern,
            "component_inventory": self.component_inventory,
            "css_variables": self.css_variables,
            "rationale": self.rationale,
            "mock_data": self.mock_data,
            "component_specs": self.component_specs,
            **self.extra,
        }


# ─── Project-type heuristics ────────────────────────────────────────────────

_PROJECT_TYPE_SIGNALS: list[tuple[list[str], str]] = [
    (["dashboard", "admin", "panel", "analytics", "management"], "dashboard"),
    (["landing", "marketing", "saas", "startup", "product"], "landing"),
    (["chat", "social", "feed", "community", "messaging"], "social"),
    (["ecommerce", "shop", "store", "cart", "checkout", "marketplace"], "ecommerce"),
    (["blog", "cms", "content", "editorial", "news"], "blog"),
    (["api", "developer", "cli", "sdk", "tool", "devtool"], "developer_tool"),
    (["health", "medical", "clinic", "patient", "ehr"], "healthcare"),
    (["finance", "banking", "wallet", "payment", "fintech"], "fintech"),
]

_FRONTEND_KEYWORDS = {
    "react", "nextjs", "next.js", "vue", "angular", "svelte",
    "html", "frontend", "ui", "web", "css", "tailwind", "interface",
}

_DESIGN_SYSTEM_PREFERENCE: dict[str, str] = {
    "dashboard":     "shadcn",
    "landing":       "shadcn", # Upgrade: Shadcn for landing sections too
    "social":        "tailwind",
    "ecommerce":     "shadcn",
    "blog":          "shadcn", # Upgrade: Professional typography
    "developer_tool": "shadcn",
    "healthcare":    "shadcn",
    "fintech":       "shadcn",
    "generic":       "shadcn", # Upgrade: Move away from vanilla
}

_PALETTES: dict[str, dict] = {
    "dashboard": {
        "primary": "#4f46e5", "primary_dark": "#3730a3", "primary_light": "#818cf8",
        "secondary": "#1e293b", "secondary_dark": "#0f172a",
        "success": "#10b981", "warning": "#f59e0b", "danger": "#ef4444", "info": "#3b82f6",
    },
    "landing": {
        "primary": "#000000", "primary_dark": "#171717", "primary_light": "#404040", # Modern tech black
        "secondary": "#ffffff", "secondary_dark": "#e5e5e5",
        "success": "#22c55e", "warning": "#f59e0b", "danger": "#ef4444", "info": "#0ea5e9",
    },
    "social": {
        "primary": "#ec4899", "primary_dark": "#be185d", "primary_light": "#f472b6",
        "secondary": "#1e293b", "secondary_dark": "#0f172a",
        "success": "#22c55e", "warning": "#f59e0b", "danger": "#ef4444", "info": "#06b6d4",
    },
    "ecommerce": {
        "primary": "#111827", "primary_dark": "#030712", "primary_light": "#374151",
        "secondary": "#3b82f6", "secondary_dark": "#2563eb",
        "success": "#22c55e", "warning": "#f59e0b", "danger": "#ef4444", "info": "#06b6d4",
    },
    "developer_tool": {
        "primary": "#0f172a", "primary_dark": "#020617", "primary_light": "#1e293b",
        "secondary": "#10b981", "secondary_dark": "#059669",
        "success": "#10b981", "warning": "#f59e0b", "danger": "#ef4444", "info": "#06b6d4",
    },
    "healthcare": {
        "primary": "#2563eb", "primary_dark": "#1e40af", "primary_light": "#60a5fa",
        "secondary": "#f8fafc", "secondary_dark": "#f1f5f9",
        "success": "#22c55e", "warning": "#f59e0b", "danger": "#ef4444", "info": "#06b6d4",
    },
    "fintech": {
        "primary": "#059669", "primary_dark": "#065f46", "primary_light": "#34d399",
        "secondary": "#111827", "secondary_dark": "#030712",
        "success": "#22c55e", "warning": "#f59e0b", "danger": "#ef4444", "info": "#06b6d4",
    },
}
_PALETTES["blog"] = _PALETTES["landing"]
_PALETTES["generic"] = _PALETTES["landing"]


def _build_css_variables(palette: dict, dark_mode: bool) -> str:
    lines = [":root {",
             f"  --color-primary:        {palette['primary']};",
             f"  --color-primary-dark:   {palette['primary_dark']};",
             f"  --color-primary-light:  {palette['primary_light']};",
             f"  --color-secondary:      {palette['secondary']};",
             f"  --color-secondary-dark: {palette['secondary_dark']};",
             f"  --color-success:  {palette['success']};",
             f"  --color-warning:  {palette['warning']};",
             f"  --color-danger:   {palette['danger']};",
             f"  --color-info:     {palette['info']};",
             "  --color-bg:           #ffffff;",
             "  --color-bg-secondary: #f8fafc;",
             "  --color-bg-tertiary:  #f1f5f9;",
             "  --color-border:       #e2e8f0;",
             "  --color-text:         #0f172a;",
             "  --color-text-muted:   #64748b;",
             "  --color-text-inverse: #ffffff;",
             "  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;",
             "  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;",
             "  --text-xs: 0.75rem; --text-sm: 0.875rem; --text-base: 1rem;",
             "  --text-lg: 1.125rem; --text-xl: 1.25rem; --text-2xl: 1.5rem;",
             "  --text-3xl: 1.875rem; --text-4xl: 2.25rem; --text-5xl: 3rem;",
             "  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px;",
             "  --radius-xl: 16px; --radius-full: 9999px;",
             "  --shadow-sm: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);",
             "  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);",
             "  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);",
             "  --transition-fast: 150ms ease-out;",
             "  --transition-normal: 250ms ease-out;",
             "}",
             ]
    if dark_mode:
        lines += [
            "",
            "[data-theme=\"dark\"], .dark {",
            "  --color-bg:           #0f172a;",
            "  --color-bg-secondary: #1e293b;",
            "  --color-bg-tertiary:  #334155;",
            "  --color-border:       #334155;",
            "  --color-text:         #f1f5f9;",
            "  --color-text-muted:   #94a3b8;",
            "}",
        ]
    return "\n".join(lines)


class UIDesignAgent:
    """
    Generates a `design_spec.json` for a project by analyzing its blueprint
    and architecture. Can operate in:
      - heuristic mode: pure Python, no AI call (fast, deterministic)
      - AI-enhanced mode: sends context to an LLM for richer, project-specific output
    """

    def __init__(self, ai_caller=None):
        """
        ai_caller: optional async callable(prompt: str, system: str) -> str
                   If provided, used to enhance the spec with AI insights.
        """
        self.ai_caller = ai_caller

    def _detect_project_type(self, blueprint: dict, architecture: dict) -> str:
        text = " ".join([
            blueprint.get("descripcion", ""),
            blueprint.get("nombre", ""),
            " ".join(blueprint.get("caracteristicas", [])),
            " ".join(
                m.get("nombre", "") + " " + m.get("descripcion", "")
                for m in architecture.get("modulos", [])
            ),
        ]).lower()

        for keywords, project_type in _PROJECT_TYPE_SIGNALS:
            if any(kw in text for kw in keywords):
                return project_type
        return "generic"

    def _has_frontend(self, architecture: dict) -> bool:
        for m in architecture.get("modulos", []):
            tech = m.get("tecnologia", "").lower()
            name = m.get("nombre", "").lower()
            tipo = m.get("tipo", "").lower()
            if any(kw in tech or kw in name or kw in tipo for kw in _FRONTEND_KEYWORDS):
                return True
        return False

    def _detect_dark_mode(self, blueprint: dict, project_type: str) -> bool:
        text = (blueprint.get("descripcion", "") + " " +
                " ".join(blueprint.get("caracteristicas", []))).lower()
        if "dark mode" in text or "dark theme" in text or "modo oscuro" in text:
            return True
        return project_type in {"developer_tool", "dashboard"}

    def _build_component_inventory(self, architecture: dict, project_type: str, layout: str) -> list[str]:
        inventory: list[str] = []
        text = " ".join(
            m.get("nombre", "") + " " + m.get("descripcion", "")
            for m in architecture.get("modulos", [])
        ).lower()

        # Always include
        if layout in ("dashboard", "app_shell"):
            inventory += ["sidebar_nav", "top_bar", "breadcrumbs"]
        elif layout == "landing":
            inventory += ["navbar", "hero_section", "footer"]
        else:
            inventory += ["navbar"]

        # Conditionally include
        if any(kw in text for kw in ["table", "list", "data", "records", "grid"]):
            inventory.append("data_table")
        if any(kw in text for kw in ["card", "item", "product", "post"]):
            inventory.append("card_grid")
        if any(kw in text for kw in ["form", "create", "edit", "input", "submit"]):
            inventory.append("form_modal")
        if any(kw in text for kw in ["chart", "graph", "analytics", "metric", "kpi"]):
            inventory += ["chart_widget", "kpi_cards"]
        if any(kw in text for kw in ["auth", "login", "register", "signup", "user"]):
            inventory += ["login_form", "register_form"]
        if any(kw in text for kw in ["notification", "alert", "message", "toast"]):
            inventory.append("toast_notification")
        if any(kw in text for kw in ["search", "filter", "query"]):
            inventory.append("search_bar")
        if any(kw in text for kw in ["upload", "file", "image", "media"]):
            inventory.append("file_upload")
        if any(kw in text for kw in ["profile", "avatar", "account", "user"]):
            inventory.append("user_avatar_menu")

        return list(dict.fromkeys(inventory))  # deduplicate, preserve order

    def _detect_layout(self, project_type: str, architecture: dict) -> str:
        if project_type in {"dashboard"}:
            return "dashboard"
        if project_type in {"landing", "blog"}:
            return "landing"
        if project_type in {"social", "ecommerce"}:
            return "app_shell"
        return "app_shell"

    def generate_spec(self, blueprint: dict, architecture: dict) -> DesignSpec:
        """Synchronous heuristic-based spec generation."""
        from kernel.design.mock_data_generator import MockDataGenerator

        project_type = self._detect_project_type(blueprint, architecture)
        layout = self._detect_layout(project_type, architecture)
        dark_mode = self._detect_dark_mode(blueprint, project_type)
        design_system = _DESIGN_SYSTEM_PREFERENCE.get(project_type, "tailwind")
        palette = _PALETTES.get(project_type, _PALETTES["generic"])
        component_inventory = self._build_component_inventory(architecture, project_type, layout)
        css_variables = _build_css_variables(palette, dark_mode)
        mock_data = MockDataGenerator.generate(project_type, blueprint, architecture)

        rationale = (
            f"Project type detected as '{project_type}'. "
            f"Layout pattern '{layout}' selected. "
            f"Design system '{design_system}' chosen for this project category. "
            f"Dark mode {'enabled' if dark_mode else 'disabled'} based on project signals."
        )

        return DesignSpec(
            design_system=design_system,
            color_palette=palette,
            typography={
                "font_sans": "Inter, system-ui, -apple-system, sans-serif",
                "font_mono": "JetBrains Mono, Fira Code, monospace",
                "heading_weight": 700,
                "body_weight": 400,
                "scale": "major_third_1.25x",
            },
            spacing_base=8,
            border_radius={"sm": "4px", "md": "8px", "lg": "12px", "xl": "16px", "full": "9999px"},
            shadows={
                "sm": "0 1px 3px 0 rgb(0 0 0 / 0.1)",
                "md": "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                "lg": "0 10px 15px -3px rgb(0 0 0 / 0.1)",
            },
            dark_mode=dark_mode,
            layout_pattern=layout,
            component_inventory=component_inventory,
            css_variables=css_variables,
            rationale=rationale,
            mock_data=mock_data,
        )

    async def generate_spec_with_ai(self, blueprint: dict, architecture: dict) -> DesignSpec:
        """AI-enhanced spec generation — falls back to heuristic if AI fails."""
        base_spec = self.generate_spec(blueprint, architecture)

        if not self.ai_caller:
            return base_spec

        _PALETTE_KEYS = {"primary", "primary_dark", "primary_light", "secondary", "secondary_dark",
                         "success", "warning", "danger", "info"}

        system = (
            "You are a senior UI/UX designer. Given a software project, output ONLY a valid JSON object "
            "(no markdown fences, no explanation, no trailing text) with these exact keys:\n"
            "\n"
            "- \"component_inventory\": list[str] — specific UI component names for this exact project\n"
            "- \"dark_mode\": boolean\n"
            "- \"rationale\": string — 2-3 sentence design rationale specific to this domain and user base\n"
            "- \"custom_palette\": object or null — if this domain warrants custom brand colors, provide "
            "an object with keys: primary, primary_dark, primary_light, secondary, secondary_dark, "
            "success, warning, danger, info (all hex values). Return null to keep the base palette.\n"
            "- \"mock_data\": object — realistic domain-specific seed data. 4-6 records per entity. "
            "Use real-looking names and values — NO 'Test User', NO 'test@test.com', NO 'Item 1'. "
            "Tailor to the actual domain (e-commerce: real product names+prices; analytics: real metric "
            "names+values; social: real user profiles+posts; fintech: real transaction descriptions).\n"
            "- \"component_specs\": list of objects, one per key component. Each object has: "
            "\"name\" (string), \"description\" (string), \"visual\" (string — describe colors, spacing, "
            "typography hierarchy, and visual effects like shadows/hover states), "
            "\"tailwind_classes\" (string — key Tailwind utility classes for the root element), "
            "\"interactions\" (string — hover, click, transition behaviors).\n"
            "\n"
            "Return ONLY the JSON object. No markdown, no code blocks, no explanation before or after."
        )

        modules_summary = [
            f"{m.get('nombre', '')}: {m.get('descripcion', '')}"
            for m in architecture.get("modulos", [])[:8]
        ]

        prompt = (
            f"Project name: {blueprint.get('nombre', 'Unknown')}\n"
            f"Description: {blueprint.get('descripcion', '')}\n"
            f"Features: {', '.join(blueprint.get('caracteristicas', []))}\n"
            f"Architecture modules:\n" + "\n".join(f"  - {m}" for m in modules_summary) + "\n\n"
            f"Base heuristic spec:\n"
            f"  layout: {base_spec.layout_pattern}\n"
            f"  design_system: {base_spec.design_system}\n"
            f"  dark_mode: {base_spec.dark_mode}\n\n"
            "Generate the full JSON. Prioritize domain specificity and visual quality over generic patterns."
        )

        try:
            raw = await self.ai_caller(prompt, system)
            # Strip any markdown fences
            raw = re.sub(r"```(?:json)?\s*", "", raw).strip().strip("`").strip()
            # Trim any trailing content after the closing brace
            last_brace = raw.rfind("}")
            if last_brace != -1:
                raw = raw[:last_brace + 1]
            ai_data = json.loads(raw)

            if "component_inventory" in ai_data and isinstance(ai_data["component_inventory"], list):
                base_spec.component_inventory = ai_data["component_inventory"]
            if "rationale" in ai_data and isinstance(ai_data["rationale"], str):
                base_spec.rationale = ai_data["rationale"]
            if "dark_mode" in ai_data and isinstance(ai_data["dark_mode"], bool):
                base_spec.dark_mode = ai_data["dark_mode"]
            if "custom_palette" in ai_data and isinstance(ai_data.get("custom_palette"), dict):
                palette = ai_data["custom_palette"]
                if _PALETTE_KEYS.issubset(palette.keys()):
                    base_spec.color_palette = palette
            if "mock_data" in ai_data and isinstance(ai_data["mock_data"], dict):
                base_spec.mock_data = ai_data["mock_data"]
            if "component_specs" in ai_data and isinstance(ai_data["component_specs"], list):
                base_spec.component_specs = ai_data["component_specs"]

            # Always rebuild CSS variables (palette may have been updated)
            base_spec.css_variables = _build_css_variables(base_spec.color_palette, base_spec.dark_mode)

        except Exception as exc:
            logger.warning("UIDesignAgent AI enhancement failed, using heuristic spec: %s", exc)

        return base_spec

    def save_spec(self, spec: DesignSpec, workspace_path: Path) -> Path:
        """Write design_spec.json to the project workspace."""
        out_path = workspace_path / "design_spec.json"
        out_path.write_text(json.dumps(spec.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("UIDesignAgent: design_spec.json saved → %s", out_path)
        return out_path

    def load_spec(self, workspace_path: Path) -> Optional[DesignSpec]:
        """Load an existing design_spec.json from the workspace."""
        spec_path = workspace_path / "design_spec.json"
        if not spec_path.exists():
            return None
        try:
            data = json.loads(spec_path.read_text(encoding="utf-8"))
            known = set(DesignSpec.__dataclass_fields__.keys())
            return DesignSpec(
                design_system=data.get("design_system", "tailwind"),
                color_palette=data.get("color_palette", {}),
                typography=data.get("typography", {}),
                spacing_base=data.get("spacing_base", 8),
                border_radius=data.get("border_radius", {}),
                shadows=data.get("shadows", {}),
                dark_mode=data.get("dark_mode", False),
                layout_pattern=data.get("layout_pattern", "app_shell"),
                component_inventory=data.get("component_inventory", []),
                css_variables=data.get("css_variables", ""),
                rationale=data.get("rationale", ""),
                mock_data=data.get("mock_data", {}),
                component_specs=data.get("component_specs", []),
                extra={k: v for k, v in data.items() if k not in known},
            )
        except Exception as exc:
            logger.warning("UIDesignAgent: failed to load design_spec.json: %s", exc)
            return None

