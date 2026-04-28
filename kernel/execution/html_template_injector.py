"""
Detects HTML/web projects and copies soda_ui.css + injects component hints
into code-generator tasks for .html files.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional


_CSS_SRC = Path(__file__).resolve().parent.parent.parent / "templates" / "html" / "soda_ui.css"

_HTML_STACKS = {"html", "web", "static", "vanilla", "bootstrap", "css", "frontend"}

COMPONENT_HINT = """
## Plantilla SODA UI disponible

El archivo `assets/soda_ui.css` ya está incluido en el proyecto. Usalo para estilizar la interfaz.
La clase raíz es `.soda-ui`. Las clases principales son:

- Layout: `.su-container`, `.su-grid`, `.su-flex`
- Navegación: `.su-nav`, `.su-nav__brand`, `.su-nav__links`
- Hero: `.su-hero`, `.su-hero__title`, `.su-hero__subtitle`
- Botones: `.su-btn` + `.su-btn--primary / --secondary / --danger / --ghost / --outline`
- Tarjetas: `.su-card`, `.su-card__header`, `.su-card__body`, `.su-card__footer`
- Badges: `.su-badge` + `.su-badge--success / --warning / --error / --info`
- Formularios: `.su-form-group`, `.su-label`, `.su-input`, `.su-select`, `.su-textarea`
- Tabla: `.su-table`
- Alertas: `.su-alert` + `.su-alert--success / --warning / --error / --info`
- Progreso: `.su-progress`, `.su-progress__bar`
- Modal: `.su-modal`, `.su-modal__content`, `.su-modal__header`, `.su-modal__body`, `.su-modal__footer`
- Toast: `.su-toast` + `.su-toast--success / --warning / --error`
- Sidebar: `.su-sidebar`, `.su-sidebar__item`
- Estadísticas: `.su-stat`, `.su-stat__value`, `.su-stat__label`
- Footer: `.su-footer`

Modo oscuro: automático via `prefers-color-scheme: dark`.
Vinculá la hoja de estilos con: `<link rel="stylesheet" href="assets/soda_ui.css">`
"""


def _is_html_project(blueprint: dict, architecture: dict) -> bool:
    stack = blueprint.get("stack_sugerido", {})
    vals = " ".join(str(v).lower() for v in stack.values())
    if any(k in vals for k in _HTML_STACKS):
        return True
    project_type = str(blueprint.get("tipo_proyecto", "")).lower()
    if any(k in project_type for k in _HTML_STACKS):
        return True
    # Check if any module file ends with .html
    for mod in architecture.get("modulos", []):
        for f in mod.get("archivos_principales", []):
            if str(f).endswith(".html"):
                return True
    return False


def inject_css(source_dir: Path) -> bool:
    """Copy soda_ui.css into source_dir/assets/. Returns True if copied."""
    if not _CSS_SRC.exists():
        return False
    dest = source_dir / "assets" / "soda_ui.css"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_CSS_SRC, dest)
    return True


def get_html_hint(filepath: str, blueprint: dict, architecture: dict) -> str:
    """Return component hint string for HTML files in HTML projects."""
    if not filepath.endswith(".html"):
        return ""
    if not _is_html_project(blueprint, architecture):
        return ""
    return COMPONENT_HINT


def inject_for_project(source_dir: Path, blueprint: dict, architecture: dict) -> bool:
    """Copy CSS to source_dir if this is an HTML project. Returns True if injected."""
    if not _is_html_project(blueprint, architecture):
        return False
    return inject_css(source_dir)
