"""
DesignContextInjector — enriches frontend module generation tasks with design spec context.

Supersedes html_template_injector.py for frontend stacks beyond plain HTML.
Supports: HTML/Vanilla, React, Vue, Angular, Next.js, Svelte.

Injects into every frontend code-generator task:
  1. CSS variables block from design_spec.json
  2. Stack-specific component patterns (Tailwind classes, shadcn imports, MUI sx, etc.)
  3. Component inventory from the design spec (what UI components to build)
  4. Layout pattern guidance (dashboard, landing, app_shell)
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Frontend stack detection ────────────────────────────────────────────────

_REACT_SIGNALS    = {"react", "jsx", "tsx", "nextjs", "next.js", "remix", "gatsby"}
_VUE_SIGNALS      = {"vue", "nuxt", "vite+vue"}
_ANGULAR_SIGNALS  = {"angular", "ng", "ngmodule"}
_SVELTE_SIGNALS   = {"svelte", "sveltekit"}
_HTML_SIGNALS     = {"html", "vanilla", "static", "web", "css", "bootstrap", "tailwind", "frontend"}

_FRONTEND_EXTENSIONS = {".html", ".css", ".jsx", ".tsx", ".vue", ".svelte", ".js", ".ts"}


def _detect_frontend_stack(module: dict, blueprint: dict) -> Optional[str]:
    """Returns one of: react | vue | angular | svelte | html | None (not frontend)."""
    tech = module.get("tecnologia", "").lower()
    name = module.get("nombre", "").lower()
    tipo = module.get("tipo", "").lower()
    text = f"{tech} {name} {tipo}"

    stack = blueprint.get("stack_sugerido", {})
    stack_text = " ".join(str(v).lower() for v in stack.values())

    combined = f"{text} {stack_text}"

    # Check file extensions too
    files_text = " ".join(str(f).lower() for f in module.get("archivos_principales", []))
    if ".jsx" in files_text or ".tsx" in files_text:
        return "react"
    if ".vue" in files_text:
        return "vue"
    if ".svelte" in files_text:
        return "svelte"
    if ".html" in files_text:
        if any(kw in combined for kw in _REACT_SIGNALS):
            return "react"

    for sig in _REACT_SIGNALS:
        if sig in combined:
            return "react"
    for sig in _VUE_SIGNALS:
        if sig in combined:
            return "vue"
    for sig in _ANGULAR_SIGNALS:
        if sig in combined:
            return "angular"
    for sig in _SVELTE_SIGNALS:
        if sig in combined:
            return "svelte"
    for sig in _HTML_SIGNALS:
        if sig in combined:
            return "html"

    return None


# ─── Stack-specific injection snippets ──────────────────────────────────────

def _build_tailwind_hint(design_system: str, dark_mode: bool) -> str:
    dm = " dark:bg-gray-900 dark:text-gray-100" if dark_mode else ""
    return f"""### Design System: {design_system.upper()}
Use Tailwind CSS utility classes. Key conventions:
- Primary action buttons: `bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white`
- Cards: `bg-white{' dark:bg-gray-800' if dark_mode else ''} rounded-xl shadow-sm border border-gray-200 p-6`
- Input fields: `w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none`
- Container: `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8`
- Responsive grid: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6`
- Body: `font-sans antialiased bg-[var(--color-bg)] text-[var(--color-text)]{dm}`
Always use CSS variables for colors (`var(--color-primary)`) or Tailwind config-mapped classes."""


def _build_shadcn_hint(dark_mode: bool) -> str:
    return f"""### Design System: shadcn/ui
Import components from `@/components/ui/`. Always use the `cn()` utility from `@/lib/utils` for conditional classes.
Key imports:
```tsx
import {{ Button }} from "@/components/ui/button"
import {{ Card, CardContent, CardHeader, CardTitle }} from "@/components/ui/card"
import {{ Input }} from "@/components/ui/input"
import {{ Badge }} from "@/components/ui/badge"
import {{ Dialog, DialogContent }} from "@/components/ui/dialog"
import {{ cn }} from "@/lib/utils"
```
Use `variant="default"` for primary, `variant="outline"` for secondary, `variant="destructive"` for danger.
{'Dark mode is active — ensure ThemeProvider wraps the app root.' if dark_mode else ''}
CSS variables from design_spec.json must be placed in `globals.css` under `:root` and `.dark`.
"""


def _build_mui_hint(dark_mode: bool) -> str:
    return f"""### Design System: Material UI (MUI)
Use `@mui/material` components. Theme setup:
```tsx
import {{ createTheme, ThemeProvider }} from '@mui/material/styles';
const theme = createTheme({{
  palette: {{
    primary: {{ main: 'var(--color-primary)' }},
    secondary: {{ main: 'var(--color-secondary)' }},
    mode: '{'dark' if dark_mode else 'light'}',
  }},
  typography: {{ fontFamily: 'Inter, system-ui, sans-serif' }},
  shape: {{ borderRadius: 8 }},
}});
```
Use `sx` prop for styling. Prefer `Box`, `Stack`, `Grid` for layout.
"""


def _build_html_hint(css_variables: str, dark_mode: bool) -> str:
    return f"""### Design System: Vanilla CSS + CSS Variables
Link the stylesheet: `<link rel="stylesheet" href="assets/styles.css">`
The following CSS variables are defined at `:root` — use them for ALL styling:
```css
{css_variables[:1200]}{'...' if len(css_variables) > 1200 else ''}
```
Never use raw hex colors or magic numbers. Always reference `var(--color-*)`, `var(--text-*)`, `var(--radius-*)`.
{'Add `data-theme="dark"` to `<html>` for dark mode.' if dark_mode else ''}
"""


_LAYOUT_HINTS: dict[str, str] = {
    "dashboard": """### Layout Pattern: Dashboard
Structure: fixed sidebar (240px) + top bar + scrollable main content.
```
┌─────────────────────────────────────────────┐
│ Sidebar (240px) │ Top Bar (search + user)    │
│                 │ ──────────────────────────  │
│ [Logo]          │ KPI Cards (3-4 per row)    │
│ Nav Item        │ ──────────────────────────  │
│ Nav Item        │ Main Chart / Data Table    │
│ Nav Item        │ ──────────────────────────  │
│                 │ Secondary content          │
└─────────────────────────────────────────────┘
```
Mobile: sidebar becomes a drawer overlay triggered by hamburger button.""",

    "landing": """### Layout Pattern: Landing Page
Structure: sticky top nav + hero section + feature sections + CTA + footer.
- Hero: full-width, centered content, primary CTA button + secondary link.
- Features: alternating image/text or 3-column icon grid.
- CTA section: high-contrast background, single headline + button.
- Footer: 4-column links + copyright.""",

    "app_shell": """### Layout Pattern: App Shell
Structure: top navigation bar + main content area.
- Top bar: logo left, nav links center/right, user avatar far right.
- Content: max-width container, scrollable.
- Mobile: hamburger menu, nav collapses to drawer.""",

    "minimal": """### Layout Pattern: Minimal
Single-column centered layout. Max-width 640–800px. Focused content, no sidebar.""",
}


# ─── Main injector ───────────────────────────────────────────────────────────

class DesignContextInjector:
    """
    Reads design_spec.json from the project workspace and builds injection
    strings to be appended to code-generator task prompts for frontend modules.
    """

    def __init__(self, workspace_path: Path):
        self.workspace_path = Path(workspace_path)
        self._spec: Optional[dict] = None

    def _load_spec(self) -> Optional[dict]:
        if self._spec is not None:
            return self._spec
        spec_path = self.workspace_path / "design_spec.json"
        if not spec_path.exists():
            return None
        try:
            self._spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("DesignContextInjector: failed to load design_spec.json: %s", exc)
            self._spec = {}
        return self._spec

    def is_available(self) -> bool:
        return (self.workspace_path / "design_spec.json").exists()

    def get_injection_for_module(self, module: dict, blueprint: dict) -> str:
        """
        Returns a design context string to append to the code-generator task
        for this module. Returns empty string if module is not frontend.
        """
        spec = self._load_spec()
        if not spec:
            return ""

        frontend_stack = _detect_frontend_stack(module, blueprint)
        if not frontend_stack:
            return ""

        design_system: str = spec.get("design_system", "tailwind")
        dark_mode: bool = spec.get("dark_mode", False)
        layout: str = spec.get("layout_pattern", "app_shell")
        css_variables: str = spec.get("css_variables", "")
        component_inventory: list = spec.get("component_inventory", [])
        palette: dict = spec.get("color_palette", {})

        parts: list[str] = ["\n\n---\n## Design Specification\n"]

        # Color palette summary
        if palette:
            parts.append(
                f"**Primary color**: `{palette.get('primary', '#3b82f6')}` "
                f"(hover: `{palette.get('primary_dark', '#2563eb')}`)\n"
                f"**Secondary**: `{palette.get('secondary', '#8b5cf6')}` | "
                f"**Success**: `{palette.get('success', '#22c55e')}` | "
                f"**Danger**: `{palette.get('danger', '#ef4444')}`"
            )

        # Component inventory
        if component_inventory:
            parts.append(
                f"\n**Component inventory** (build these UI components):\n"
                + "\n".join(f"- {c}" for c in component_inventory)
            )

        # Layout pattern
        layout_hint = _LAYOUT_HINTS.get(layout, _LAYOUT_HINTS["app_shell"])
        parts.append(f"\n{layout_hint}")

        # Stack-specific design system hint
        if frontend_stack == "html":
            parts.append(_build_html_hint(css_variables, dark_mode))
        elif frontend_stack in {"react", "vue", "svelte", "angular"}:
            if design_system == "shadcn":
                parts.append(_build_shadcn_hint(dark_mode))
            elif design_system == "mui":
                parts.append(_build_mui_hint(dark_mode))
            else:
                parts.append(_build_tailwind_hint(design_system, dark_mode))
        else:
            parts.append(_build_tailwind_hint(design_system, dark_mode))

        # CSS variables block (for all stacks — always define the tokens)
        if css_variables and frontend_stack != "html":
            parts.append(
                f"\n**CSS Variables** — define these in your root stylesheet:\n"
                f"```css\n{css_variables[:800]}{'...' if len(css_variables) > 800 else ''}\n```"
            )

        # Dark mode instruction
        if dark_mode:
            parts.append(
                "\n**Dark mode**: REQUIRED. Implement full dark mode support using "
                "CSS `[data-theme=\"dark\"]` or Tailwind `dark:` variants. "
                "Provide a toggle button that sets `document.documentElement.dataset.theme = 'dark'`."
            )

        return "\n".join(parts)

    def get_css_variables(self) -> str:
        """Return only the CSS variables block (for HTML projects)."""
        spec = self._load_spec()
        if not spec:
            return ""
        return spec.get("css_variables", "")

    def get_design_system(self) -> str:
        """Return the design system name."""
        spec = self._load_spec()
        if not spec:
            return "tailwind"
        return spec.get("design_system", "tailwind")
