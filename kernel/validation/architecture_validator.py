"""
ArchitectureValidator: validates and auto-repairs architecture.json before code generation.

What it checks (mechanically, no AI needed):
  - Required module fields exist
  - Duplicate module names
  - File paths: forward slashes, no traversal, no absolute paths, no forbidden chars
  - Duplicate file paths across modules (would cause silent overwrites)
  - Dependency cross-references: every dep name must match an existing module
  - Self-dependencies
  - Contract references: modulo_origen / modulo_destino must exist
  - Config fields: ports in valid range, commands non-empty

Auto-fixes silently (logged in auto_fixes):
  - Slash normalization
  - Leading ./ or / stripping
  - Self-dependency removal
  - Invalid dep removal (name not found)
  - Invalid contract removal
  - Missing list fields initialized to []

Errors (is_valid=False) stop the pipeline:
  - Not a dict
  - Missing or empty 'modulos'
  - Module without 'nombre'
"""

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    auto_fixes: list[str] = field(default_factory=list)
    fixed_architecture: dict = field(default_factory=dict)

    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(es) crítico(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} advertencia(s)")
        if self.auto_fixes:
            parts.append(f"{len(self.auto_fixes)} corrección(es) automática(s)")
        return ", ".join(parts) if parts else "OK"


class ArchitectureValidator:
    # Windows/filesystem forbidden characters in filenames
    _FORBIDDEN_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
    # Valid port range
    _PORT_MIN = 1024
    _PORT_MAX = 65535

    def validate(self, architecture: dict, blueprint: Optional[dict] = None) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if not isinstance(architecture, dict):
            result.is_valid = False
            result.errors.append("La arquitectura no es un objeto JSON válido.")
            result.fixed_architecture = {}
            return result

        modulos = architecture.get("modulos")
        if not isinstance(modulos, list) or not modulos:
            result.is_valid = False
            result.errors.append("La arquitectura no contiene 'modulos' o la lista está vacía.")
            result.fixed_architecture = architecture
            return result

        arch = copy.deepcopy(architecture)

        self._validate_modulos(arch, result)
        self._validate_contracts(arch, result)
        self._validate_config(arch, blueprint, result)
        self._validate_build_infrastructure(arch, blueprint, result)

        result.fixed_architecture = arch
        return result

    # ------------------------------------------------------------------ passes

    def _validate_modulos(self, arch: dict, result: ValidationResult) -> None:
        modulos = arch["modulos"]
        valid_names: set[str] = set()
        cleaned: list[dict] = []

        # Pass 1: names + required fields
        for i, mod in enumerate(modulos):
            if not isinstance(mod, dict):
                result.warnings.append(f"Módulo #{i} no es un objeto — ignorado.")
                continue

            nombre = str(mod.get("nombre", "")).strip()
            if not nombre:
                result.is_valid = False
                result.errors.append(f"Módulo #{i} sin campo 'nombre' — error crítico.")
                continue

            if nombre in valid_names:
                result.warnings.append(f"Módulo duplicado '{nombre}' — se descarta el segundo.")
                continue

            valid_names.add(nombre)

            for list_field in ("archivos_principales", "dependencias"):
                if not isinstance(mod.get(list_field), list):
                    original = mod.get(list_field)
                    mod[list_field] = [original] if isinstance(original, str) and original else []
                    result.auto_fixes.append(
                        f"[{nombre}] '{list_field}' no era lista — convertido."
                    )

            if not str(mod.get("responsabilidad", "")).strip():
                result.warnings.append(
                    f"[{nombre}] Falta 'responsabilidad' — la generación de código puede ser imprecisa."
                )

            cleaned.append(mod)

        arch["modulos"] = cleaned

        # Pass 2: normalize file paths
        all_files: dict[str, str] = {}  # normalized_path -> module_name
        for mod in arch["modulos"]:
            nombre = mod["nombre"]
            good_paths: list[str] = []
            for raw in mod.get("archivos_principales", []):
                normalized, issue = self._normalize_path(str(raw).strip())
                if issue:
                    result.warnings.append(f"[{nombre}] Ruta ignorada '{raw}': {issue}")
                    continue
                if normalized != str(raw).strip():
                    result.auto_fixes.append(
                        f"[{nombre}] Ruta normalizada: '{raw}' → '{normalized}'"
                    )
                if normalized in all_files:
                    result.warnings.append(
                        f"[{nombre}] Ruta duplicada '{normalized}' — ya declarada en "
                        f"'{all_files[normalized]}' (posible sobreescritura)."
                    )
                else:
                    all_files[normalized] = nombre
                    good_paths.append(normalized)
            mod["archivos_principales"] = good_paths

        # Pass 3: dependency cross-references
        for mod in arch["modulos"]:
            nombre = mod["nombre"]
            valid_deps: list[str] = []
            for dep in mod.get("dependencias", []):
                dep_str = str(dep).strip()
                if dep_str == nombre:
                    result.auto_fixes.append(f"[{nombre}] Auto-dependencia eliminada.")
                    continue
                if dep_str not in valid_names:
                    result.warnings.append(
                        f"[{nombre}] Dependencia '{dep_str}' no existe en la arquitectura — eliminada."
                    )
                    continue
                valid_deps.append(dep_str)
            mod["dependencias"] = valid_deps

    def _validate_contracts(self, arch: dict, result: ValidationResult) -> None:
        contratos = arch.get("contratos")
        if not isinstance(contratos, list):
            if contratos is not None:
                arch["contratos"] = []
                result.auto_fixes.append("'contratos' no era lista — inicializado a [].")
            return

        valid_names = {m["nombre"] for m in arch["modulos"] if isinstance(m, dict) and m.get("nombre")}
        good: list[dict] = []
        for c in contratos:
            if not isinstance(c, dict):
                continue
            origen = str(c.get("modulo_origen", "")).strip()
            destino = str(c.get("modulo_destino", "")).strip()
            if not origen or not destino:
                result.warnings.append("Contrato sin modulo_origen o modulo_destino — eliminado.")
                continue
            if origen not in valid_names:
                result.warnings.append(
                    f"Contrato: modulo_origen '{origen}' no existe — eliminado."
                )
                continue
            if destino not in valid_names:
                result.warnings.append(
                    f"Contrato: modulo_destino '{destino}' no existe — eliminado."
                )
                continue
            good.append(c)

        removed = len(contratos) - len(good)
        if removed:
            result.auto_fixes.append(f"{removed} contrato(s) con referencias inválidas eliminado(s).")
        arch["contratos"] = good

    def _validate_config(self, arch: dict, blueprint: Optional[dict], result: ValidationResult) -> None:
        if not blueprint:
            return

        # Commands are no longer stored in the blueprint (derived from filesystem at boot time).
        # Only validate ports if a legacy run command is present.
        run_cmd = str(blueprint.get("comando_ejecucion", "")).strip()

        # Extract and validate explicit ports from run command (legacy blueprints only)
        for port_str in re.findall(r'(?:--port|-p|port\s*=|:)\s*(\d{2,5})', run_cmd):
            port = int(port_str)
            if not (self._PORT_MIN <= port <= self._PORT_MAX):
                result.warnings.append(
                    f"Puerto {port} en 'comando_ejecucion' fuera de rango válido "
                    f"({self._PORT_MIN}-{self._PORT_MAX})."
                )

        # Check stack coherence: if stack declares a language, modules should have matching files
        stack = blueprint.get("stack_sugerido", {})
        if isinstance(stack, dict):
            backend = str(stack.get("backend", "")).lower()
            all_files = [
                f for m in arch.get("modulos", [])
                for f in m.get("archivos_principales", [])
            ]
            if "fastapi" in backend or "flask" in backend or "django" in backend:
                has_py = any(f.endswith(".py") for f in all_files)
                if not has_py:
                    result.warnings.append(
                        f"Stack declara backend Python ({backend}) pero no hay archivos .py en la arquitectura."
                    )
            if "express" in backend or "nest" in backend or "next" in backend:
                has_js = any(f.endswith((".js", ".ts")) for f in all_files)
                if not has_js:
                    result.warnings.append(
                        f"Stack declara backend Node ({backend}) pero no hay archivos .js/.ts en la arquitectura."
                    )

    # ------------------------------------------------ build infrastructure check

    # Required files per compiled language that must appear somewhere in the architecture
    _BUILD_INFRA: dict[str, dict] = {
        "cpp": {
            "marker_exts": {".cpp", ".cxx", ".cc", ".c", ".h", ".hpp"},
            "required_files": ["CMakeLists.txt", ".vscode/tasks.json", ".vscode/launch.json", ".vscode/c_cpp_properties.json"],
            "infra_module": {
                "nombre": "infraestructura_build",
                "responsabilidad": "Sistema de build CMake y configuración de VS Code para compilar, debuggear y correr el proyecto",
                "archivos_principales": [
                    "CMakeLists.txt",
                    ".vscode/tasks.json",
                    ".vscode/launch.json",
                    ".vscode/c_cpp_properties.json",
                    "README.md",
                ],
                "dependencias": [],
                "endpoints": [],
            },
        },
        "rust": {
            "marker_exts": {".rs"},
            "required_files": ["Cargo.toml"],
            "infra_module": {
                "nombre": "infraestructura_build",
                "responsabilidad": "Manifiesto Cargo y configuración de VS Code para el proyecto Rust",
                "archivos_principales": ["Cargo.toml", ".vscode/tasks.json", ".vscode/launch.json", "README.md"],
                "dependencias": [],
                "endpoints": [],
            },
        },
        "go": {
            "marker_exts": {".go"},
            "required_files": ["go.mod"],
            "infra_module": {
                "nombre": "infraestructura_build",
                "responsabilidad": "Módulo Go y configuración de VS Code para el proyecto Go",
                "archivos_principales": ["go.mod", ".vscode/tasks.json", ".vscode/launch.json", "README.md"],
                "dependencias": [],
                "endpoints": [],
            },
        },
    }

    def _validate_build_infrastructure(
        self, arch: dict, blueprint: Optional[dict], result: ValidationResult
    ) -> None:
        all_files = [
            f for m in arch.get("modulos", [])
            for f in m.get("archivos_principales", [])
        ]
        all_files_set = set(all_files)

        # Detect language from file extensions
        detected_lang: Optional[str] = None
        for lang, cfg in self._BUILD_INFRA.items():
            exts = cfg["marker_exts"]
            if any(Path(f).suffix.lower() in exts for f in all_files):
                detected_lang = lang
                break

        # Also detect from blueprint stack if no source files found yet
        if not detected_lang and blueprint:
            stack_text = json.dumps(blueprint.get("stack_sugerido", {})).lower()
            desc_text = (blueprint.get("descripcion", "") + " " + json.dumps(blueprint.get("funcionalidades", []))).lower()
            combined = stack_text + " " + desc_text
            if any(kw in combined for kw in ("c++", "cpp", "cmake", "win32", "winapi", "opengl", "directx")):
                detected_lang = "cpp"
            elif "rust" in combined or "cargo" in combined:
                detected_lang = "rust"
            elif any(kw in combined for kw in ("golang", " go ", "go lang")):
                detected_lang = "go"

        if not detected_lang:
            return

        cfg = self._BUILD_INFRA[detected_lang]
        missing = [f for f in cfg["required_files"] if f not in all_files_set]

        if not missing:
            return

        # Check if there's already an infra module we can augment
        existing_infra = next(
            (m for m in arch["modulos"] if "infraestructura" in m.get("nombre", "").lower() or "build" in m.get("nombre", "").lower()),
            None,
        )

        if existing_infra:
            # Inject missing files into the existing infra module
            existing_files = set(existing_infra.get("archivos_principales", []))
            added = [f for f in cfg["infra_module"]["archivos_principales"] if f not in existing_files]
            existing_infra["archivos_principales"] = list(existing_files) + added
            result.auto_fixes.append(
                f"[{detected_lang.upper()}] Módulo '{existing_infra['nombre']}' completado con archivos de build faltantes: {added}"
            )
        else:
            # Inject a full infraestructura_build module at position 0
            arch["modulos"].insert(0, copy.deepcopy(cfg["infra_module"]))
            result.auto_fixes.append(
                f"[{detected_lang.upper()}] Módulo 'infraestructura_build' inyectado automáticamente con: "
                f"{cfg['infra_module']['archivos_principales']}"
            )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _normalize_path(raw: str) -> tuple[str, str]:
        """Returns (normalized_path, error_reason). error_reason is '' if OK."""
        if not raw:
            return "", "ruta vacía"

        p = raw.replace("\\", "/")

        # Strip leading ./ and /
        while p.startswith("./"):
            p = p[2:]
        p = p.lstrip("/")

        if not p:
            return "", "ruta queda vacía tras normalización"

        # Reject traversal
        if "../" in p or p.startswith(".."):
            return "", "contiene traversal (../)"

        # Reject absolute Windows paths (C:/, D:/, etc.)
        if re.match(r'^[A-Za-z]:', p):
            return "", "ruta absoluta con letra de unidad"

        # Reject forbidden characters (Windows filesystem)
        if ArchitectureValidator._FORBIDDEN_CHARS.search(p):
            return "", "contiene caracteres inválidos para el sistema de archivos"

        # Warn-worthy but not blocked: spaces in paths
        # (returned as valid but caller can warn separately)

        return p, ""
