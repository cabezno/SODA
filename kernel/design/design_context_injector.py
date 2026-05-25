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
    dm_card = " dark:bg-gray-800 dark:border-gray-700" if dark_mode else ""
    dm_input = " dark:bg-gray-800 dark:border-gray-600 dark:text-gray-100" if dark_mode else ""
    dm_body = " dark:bg-gray-900 dark:text-gray-100" if dark_mode else ""
    return f"""### Design System: {design_system.upper()} — Tailwind CSS
**Utility class conventions:**
- Primary button: `inline-flex items-center gap-2 px-4 py-2 bg-[var(--color-primary)] hover:bg-[var(--color-primary-dark)] text-white text-sm font-medium rounded-lg transition-colors duration-150 shadow-sm`
- Secondary/outline button: `inline-flex items-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors duration-150`
- Card container: `bg-white{dm_card} rounded-xl shadow-sm border border-gray-200 p-6 transition-shadow hover:shadow-md`
- Input field: `w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white{dm_input} placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent transition-shadow`
- Page container: `max-w-7xl mx-auto px-4 sm:px-6 lg:px-8`
- Section heading: `text-2xl font-bold text-gray-900 tracking-tight`
- Subheading: `text-sm font-medium text-gray-500 uppercase tracking-wider`
- Responsive card grid: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5`
- Status badge (success): `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700`
- Status badge (warning): `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700`
- Status badge (danger): `inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700`
- Body: `font-sans antialiased bg-[var(--color-bg)] text-[var(--color-text)]{dm_body}`
- Divider: `border-t border-gray-200{' dark:border-gray-700' if dark_mode else ''}`
Always reference CSS variables (`var(--color-primary)`) for brand colors. Use Tailwind for spacing/layout."""


def _build_shadcn_hint(dark_mode: bool) -> str:
    return f"""### Design System: shadcn/ui + Tailwind CSS
Import from `@/components/ui/`. Always use `cn()` from `@/lib/utils` for conditional classes.

**Key imports:**
```tsx
import {{ Button }} from "@/components/ui/button"
import {{ Card, CardContent, CardHeader, CardTitle, CardDescription }} from "@/components/ui/card"
import {{ Input }} from "@/components/ui/input"
import {{ Label }} from "@/components/ui/label"
import {{ Badge }} from "@/components/ui/badge"
import {{ Avatar, AvatarFallback, AvatarImage }} from "@/components/ui/avatar"
import {{ Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger }} from "@/components/ui/dialog"
import {{ DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger }} from "@/components/ui/dropdown-menu"
import {{ Table, TableBody, TableCell, TableHead, TableHeader, TableRow }} from "@/components/ui/table"
import {{ Separator }} from "@/components/ui/separator"
import {{ Skeleton }} from "@/components/ui/skeleton"
import {{ cn }} from "@/lib/utils"
```

**Usage patterns:**
- Primary CTA: `<Button>` (default variant, size="lg" for hero CTAs)
- Ghost/nav links: `<Button variant="ghost" size="sm">`
- Danger actions: `<Button variant="destructive">`
- Status pills: `<Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">Active</Badge>`
- Loading state: `<Skeleton className="h-4 w-full rounded" />`
- Modal: `<Dialog>` with `<DialogTrigger asChild>`

{'**Dark mode REQUIRED**: wrap app root with `<ThemeProvider attribute="class">`. Toggle via `useTheme()` hook. All shadcn components handle dark mode automatically via Tailwind `dark:` variants.' if dark_mode else ''}
CSS variables from design_spec.json go into `globals.css` under `:root` (and `.dark` if dark_mode).
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


# ─── Component inventory detail descriptions ─────────────────────────────────

_COMPONENT_DETAIL: dict[str, str] = {
    "sidebar_nav": "Fixed sidebar (240px). Logo at top, nav items with icon+label, active state uses primary color bg. User profile at bottom. On mobile: hidden, toggled via hamburger button as a drawer overlay.",
    "top_bar": "Full-width header with search input (center), notification bell (badge count), and user avatar dropdown (far right). Height 64px, white bg, bottom border.",
    "breadcrumbs": "Horizontal path trail. Each segment is a link except the last (current page). Separator: `/` or `>`. Font: text-sm text-muted-foreground.",
    "navbar": "Sticky top nav. Logo left, nav links center/right, primary CTA button far right. On scroll: adds shadow. Mobile: hamburger → slide-down menu.",
    "hero_section": "Full-width, vertically centered. Large bold headline (text-5xl), subheadline (text-xl text-gray-500), primary+secondary CTA buttons (gap-4). Optional: gradient background, stats row below, floating screenshot/mockup image.",
    "footer": "4-column links grid + copyright row. Columns: Product, Company, Resources, Legal. Bottom: social icons + theme toggle.",
    "data_table": "Sortable columns (click header to sort, show arrow icon). Pagination (prev/next + page count). Each row: hover state bg-gray-50. Status column uses color-coded Badge. Action column has icon button (MoreHorizontal dropdown).",
    "card_grid": "Responsive grid (1→2→3 cols). Each card: image top, content (title, description, meta), footer (price/date + action button). Hover: shadow-md + slight translateY(-2px).",
    "form_modal": "Dialog with max-w-md. Form fields with Label + Input pairs. Validation errors shown below input in text-red-500 text-sm. Footer: Cancel (outline) + Submit (primary) buttons.",
    "chart_widget": "Card wrapper. Chart title + time period selector (tabs or select). Chart fills remaining height. Use recharts or Chart.js. Show skeleton while loading.",
    "kpi_cards": "4-column responsive grid. Each card: metric label (text-sm text-muted), large value (text-3xl font-bold), trend row (arrow icon + percentage + period text). Colored top border (emerald=up, red=down).",
    "login_form": "Centered card (max-w-sm). Logo/app name. Email + password inputs. 'Forgot password?' link. Primary submit button (full width). Divider + OAuth buttons (Google, GitHub). Link to register.",
    "register_form": "Similar to login. Name + email + password + confirm fields. Password strength indicator. Terms checkbox. Link back to login.",
    "toast_notification": "Fixed bottom-right, stacked. Variants: success (green), error (red), warning (amber), info (blue). Auto-dismiss after 4s with progress bar. Close button.",
    "search_bar": "Input with magnifier icon left, clear (×) button right. On focus: ring + dropdown with recent searches or live results.",
    "file_upload": "Drag-and-drop zone (dashed border, cloud icon). Accepted formats + size limit shown. Progress bar while uploading. Uploaded file list with remove button.",
    "user_avatar_menu": "Avatar button (32px circle, initials fallback). Dropdown: Profile, Settings, Divider, Sign out. Show user name + email at top.",
}


def _build_component_inventory_detail(component_inventory: list) -> str:
    """Maps component names to rich design descriptions for coders."""
    lines = []
    for name in component_inventory:
        detail = _COMPONENT_DETAIL.get(name)
        if detail:
            lines.append(f"- **{name}**: {detail}")
        else:
            lines.append(f"- **{name}**")
    return "\n".join(lines)


def _build_mock_data_hint(mock_data: dict, stack_or_lang: str, label: str = "Mock Data — use these realistic seed values in your initial render") -> str:
    """
    Formats domain-specific mock data as inline constants.
    stack_or_lang: frontend stack (react/vue/svelte/angular/html) or backend lang (python/go/typescript/nodejs)
    """
    if not mock_data:
        return ""
    try:
        s = stack_or_lang.lower()
        # C++ and other compiled/native languages: mock data doesn't apply
        if s in {"cpp", "c++", "cmake", "rust", "go", "golang", "java", "kotlin", "swift"}:
            return ""
        is_ts  = s in {"react", "vue", "svelte", "angular", "nestjs", "nodejs", "typescript"}
        is_html = s == "html"
        is_python = s in {"python", "fastapi"}

        lines = [f"\n### {label}\n"]

        if is_ts:
            lines.append("```typescript")
            for entity, records in list(mock_data.items())[:4]:
                const_name = "MOCK_" + entity.upper().replace("-", "_")
                lines.append(f"export const {const_name} = {json.dumps(records, indent=2, ensure_ascii=False)} as const;")
            lines.append("```")
        elif is_html:
            lines.append("```javascript")
            for entity, records in list(mock_data.items())[:4]:
                const_name = entity.upper().replace("-", "_")
                lines.append(f"const {const_name} = {json.dumps(records, indent=2, ensure_ascii=False)};")
            lines.append("```")
        else:
            # Python or any other backend lang — use Python dict syntax
            lines.append("```python")
            for entity, records in list(mock_data.items())[:4]:
                const_name = "MOCK_" + entity.upper().replace("-", "_")
                lines.append(f"{const_name} = {json.dumps(records, indent=2, ensure_ascii=False)}")
            lines.append("```")

        return "\n".join(lines)
    except Exception:
        return ""


def _build_component_specs_hint(component_specs: list) -> str:
    """Formats AI-generated component design specs for the coder."""
    if not component_specs:
        return ""
    parts = ["\n### Component Design Specifications\n"]
    for spec in component_specs[:6]:
        if not isinstance(spec, dict):
            continue
        name = spec.get("name", "?")
        parts.append(f"**{name}**")
        if spec.get("description"):
            parts.append(f"  Purpose: {spec['description']}")
        if spec.get("visual"):
            parts.append(f"  Visual: {spec['visual']}")
        if spec.get("tailwind_classes"):
            parts.append(f"  Root classes: `{spec['tailwind_classes']}`")
        if spec.get("interactions"):
            parts.append(f"  Interactions: {spec['interactions']}")
        parts.append("")
    return "\n".join(parts)


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

        component_specs: list = spec.get("component_specs", [])
        mock_data: dict = spec.get("mock_data", {})

        parts: list[str] = ["\n\n---\n## Design Specification\n"]

        # Color palette summary
        if palette:
            parts.append(
                f"**Colors** — Primary: `{palette.get('primary', '#3b82f6')}` "
                f"(hover: `{palette.get('primary_dark', '#2563eb')}`, "
                f"light: `{palette.get('primary_light', '#93c5fd')}`)\n"
                f"Secondary: `{palette.get('secondary', '#1e293b')}` | "
                f"Success: `{palette.get('success', '#22c55e')}` | "
                f"Warning: `{palette.get('warning', '#f59e0b')}` | "
                f"Danger: `{palette.get('danger', '#ef4444')}`"
            )

        # Component inventory with rich descriptions
        if component_inventory:
            parts.append(
                f"\n**Components to build** (implement ALL of these):\n"
                + _build_component_inventory_detail(component_inventory)
            )

        # AI-generated component specs (visual details)
        if component_specs:
            parts.append(_build_component_specs_hint(component_specs))

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
                f"\n**CSS Variables** — define these in your root stylesheet (`globals.css` or equivalent):\n"
                f"```css\n{css_variables}\n```"
            )

        # Mock data — realistic seed content
        if mock_data:
            parts.append(_build_mock_data_hint(mock_data, frontend_stack))

        # Dark mode instruction
        if dark_mode:
            parts.append(
                "\n**Dark mode REQUIRED**: Implement full dark mode support. "
                "Use Tailwind `dark:` variants or CSS `[data-theme=\"dark\"]`. "
                "Provide a toggle button in the top bar that calls "
                "`document.documentElement.classList.toggle('dark')` or `setTheme('dark')`."
            )

        # Quality bar reminder
        parts.append(
            "\n**Quality bar**: The generated UI must look production-ready. "
            "Use proper visual hierarchy (heading sizes, font weights, color contrast). "
            "Add hover/focus states to all interactive elements. "
            "Show loading skeletons instead of blank states. "
            "Use the mock data above for realistic content — never use 'Lorem ipsum' or 'Test User'."
        )

        return "\n".join(parts)

    def get_backend_data_injection(self, lang: str) -> str:
        """
        Returns a mock data injection for backend modules (Python, Go, TypeScript/NestJS).
        Uses the same domain-specific data from design_spec.json so that seed scripts,
        fixtures, and API example responses look real — not 'Test User 1' or 'Item 1'.
        Returns empty string if no design spec or no mock data.
        """
        spec = self._load_spec()
        if not spec:
            return ""
        mock_data = spec.get("mock_data", {})
        if not mock_data:
            return ""

        label = "Seed / fixture data — use these realistic values in database seeders, factory functions, and example API responses"
        return _build_mock_data_hint(mock_data, lang, label=label)

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
