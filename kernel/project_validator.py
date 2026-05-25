"""
ProjectValidator: setup environment, run build checks, auto-fix errors.

Loop: setup → build → [error → AI fix → rebuild] × MAX_ROUNDS → done
"""
import asyncio
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional


class ProjectValidator:
    MAX_FIX_ROUNDS = 3
    BUILD_TIMEOUT  = 120  # seconds per build attempt
    SETUP_TIMEOUT  = 180  # seconds for env setup

    def __init__(
        self,
        gemini_driver,
        context_builder,
        notify_fn: Callable = None,
    ):
        self.gemini  = gemini_driver
        self.gemini  = gemini_driver
        self.builder = context_builder
        self.notify  = notify_fn or (lambda *a, **kw: None)

    # ------------------------------------------------------------------ setup

    async def setup_environment(self, source_dir: Path, install_cmd: str, run_cmd: str) -> tuple[bool, str]:
        """Create venv (Python) / restore packages / configure+build C++ CMake projects."""
        ic = (install_cmd or "").lower()
        rc = (run_cmd or "").lower()
        is_python = "pip" in ic or any(x in rc for x in ("python", "uvicorn", "flask", "gunicorn", "fastapi", "django"))
        is_node   = any(x in ic for x in ("npm", "yarn", "pnpm")) or any(x in rc for x in ("npm ", "yarn ", "node "))
        is_dotnet = "dotnet" in ic or "dotnet" in rc
        is_go     = "go mod" in ic or "go run" in rc or "go build" in rc
        is_cmake  = (source_dir / "CMakeLists.txt").exists() or "cmake" in ic or "cmake" in rc
        is_cargo  = (source_dir / "Cargo.toml").exists() or "cargo" in ic or "cargo" in rc

        out = []

        try:
            if is_cmake:
                ok, msg = await self._setup_cmake(source_dir)
                out.append(msg)
                if not ok:
                    return False, "\n".join(out)
                return True, "\n".join(out)

            if is_cargo:
                r = await self._run(["cargo", "build", "--release"], source_dir, timeout=300)
                out.append(r[1])
                return r[0] == 0, "\n".join(out)

            if is_python:
                venv = source_dir / "venv"
                if not venv.exists():
                    r = await self._run(["python", "-m", "venv", "venv"], source_dir, timeout=60)
                    out.append(r[1])
                    if r[0] != 0:
                        return False, "\n".join(out)

                pip = str(source_dir / "venv" / "Scripts" / "pip.exe")
                req = next(
                    (f for f in ("requirements.txt", "requirements/base.txt", "requirements/main.txt")
                     if (source_dir / f).exists()),
                    None,
                )
                if req:
                    r = await self._run([pip, "install", "-r", req, "--quiet"], source_dir)
                    out.append(r[1])
                    if r[0] != 0:
                        return False, "\n".join(out)
                elif (source_dir / "pyproject.toml").exists() or (source_dir / "setup.py").exists():
                    r = await self._run([pip, "install", ".", "--quiet"], source_dir)
                    out.append(r[1])

            elif is_node:
                r = await self._run(["npm", "install"], source_dir)
                out.append(r[1])
                if r[0] != 0:
                    return False, "\n".join(out)

            elif is_dotnet:
                r = await self._run(["dotnet", "restore"], source_dir)
                out.append(r[1])

            elif is_go:
                if (source_dir / "go.mod").exists():
                    r = await self._run(["go", "mod", "download"], source_dir)
                    out.append(r[1])

        except Exception as e:
            return False, f"Setup error: {e}"

        return True, "\n".join(out)

    # ---------------------------------------------------------- build check

    def detect_check_command(self, source_dir: Path, run_cmd: str, install_cmd: str) -> Optional[list[str]]:
        rc = (run_cmd or "").lower()
        ic = (install_cmd or "").lower()

        if "dotnet" in rc or "dotnet" in ic:
            return ["dotnet", "build", "--nologo", "-v", "quiet"]

        if any(x in rc for x in ("npm ", "yarn ", "node ", "npx ")):
            if (source_dir / "tsconfig.json").exists():
                return ["npx", "tsc", "--noEmit"]
            pkg = source_dir / "package.json"
            if pkg.exists():
                try:
                    scripts = json.loads(pkg.read_text()).get("scripts", {})
                    if "build" in scripts:
                        return ["npm", "run", "build"]
                    if "typecheck" in scripts:
                        return ["npm", "run", "typecheck"]
                except Exception:
                    pass
            return None  # pure JS — no reliable static check

        if "pip" in ic or any(x in rc for x in ("python", "uvicorn", "flask", "gunicorn", "fastapi", "django")):
            venv_python = source_dir / "venv" / "Scripts" / "python.exe"
            py = str(venv_python) if venv_python.exists() else "python"
            return [py, "-m", "compileall", "-q", "."]

        if "go run" in rc or "go build" in rc:
            return ["go", "build", "./..."]

        if "cargo" in rc:
            return ["cargo", "build", "--quiet"]

        if "mvn" in rc or "mvn" in ic:
            return ["mvn", "compile", "-q"]

        return None

    async def run_build_check(self, source_dir: Path, check_cmd: list[str]) -> tuple[bool, str]:
        code, output = await self._run(check_cmd, source_dir)
        return code == 0, output

    # ------------------------------------------------------------ AI fixes

    def _collect_sources(self, source_dir: Path, max_chars: int = 40_000) -> str:
        skip_dirs = {"venv", "node_modules", ".git", "__pycache__", "bin", "obj",
                     "target", ".gradle", ".vs", "dist", "build", ".next"}
        text_exts = {
            ".py", ".js", ".ts", ".jsx", ".tsx", ".cs", ".go", ".java", ".php",
            ".rb", ".rs", ".swift", ".cpp", ".c", ".h",
            ".html", ".css", ".json", ".yaml", ".yml", ".toml", ".xml", ".md", ".env",
        }
        parts = []
        total = 0
        for p in sorted(source_dir.rglob("*")):
            if p.is_dir():
                continue
            if any(part in skip_dirs for part in p.parts):
                continue
            if p.name.startswith("_soda_") or p.suffix.lower() not in text_exts:
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = str(p.relative_to(source_dir)).replace("\\", "/")
                chunk = f"### {rel}\n{content[:4000]}"
                parts.append(chunk)
                total += len(chunk)
                if total >= max_chars:
                    break
            except Exception:
                continue
        return "\n\n".join(parts)

    async def _ask_for_fixes(
        self,
        source_dir: Path,
        build_errors: str,
        project_description: str,
        architecture: Optional[dict] = None,
    ) -> list[dict]:
        sources = self._collect_sources(source_dir)
        arch_text = json.dumps(architecture or {}, ensure_ascii=False, indent=2)
        # Normalize absolute paths in build errors to relative ones so the AI
        # returns paths that match the ### headers in sources (relative to source_dir).
        normalized_errors = build_errors
        src_str = str(source_dir).replace("\\", "/")
        normalized_errors = normalized_errors.replace(str(source_dir), "").replace(src_str, "")
        task = (
            f"DESCRIPCIÓN DEL PROYECTO:\n{project_description}\n\n"
            f"ARQUITECTURA ACTUAL:\n{arch_text}\n\n"
            f"ERRORES DE BUILD:\n{normalized_errors[:6000]}\n\n"
            f"ARCHIVOS DEL PROYECTO (paths relativos a source/):\n"
            f"IMPORTANTE: el campo 'file' de tu respuesta JSON debe coincidir EXACTAMENTE "
            f"con el path del header ### correspondiente (ej: si el header es ### src/main.py, "
            f"devolvé \"file\": \"src/main.py\").\n\n"
            f"{sources}"
        )
        from kernel.utils.ai_fallback import is_capacity_error
        ai_failures: list[str] = []
        for driver, provider in [(self.gemini, "gemini"), (self.gemini, "gemini")]:
            if driver is None:
                continue
            try:
                payload = self.builder.build_payload(provider, "code_fixer", task)
                result = (await driver.call(payload["system"], payload["user"])).content
            except Exception as exc:
                ai_failures.append(f"{provider}: {type(exc).__name__}: {exc}")
                self.notify(
                    f"ProjectValidator: {provider} lanzó excepción: {exc}",
                    "HEALTH_WARN",
                    {"phase": "validation_fix", "provider": provider, "error": str(exc)},
                )
                continue
            if is_capacity_error(result) or result.startswith("ERROR:"):
                ai_failures.append(f"{provider}: {result[:200]}")
                self.notify(
                    f"ProjectValidator: {provider} retornó error de capacidad/API: {result[:200]}",
                    "HEALTH_WARN",
                    {"phase": "validation_fix", "provider": provider, "response": result[:500]},
                )
                continue
            fixes = self._parse_fixes(result)
            if fixes:
                return fixes
            ai_failures.append(f"{provider}: respuesta sin JSON parseable")
            self.notify(
                f"ProjectValidator: {provider} respondió pero sin fixes parseables (respuesta: {result[:300]})",
                "HEALTH_WARN",
                {"phase": "validation_fix", "provider": provider, "response_snippet": result[:800]},
            )
        if ai_failures:
            self.notify(
                f"ProjectValidator: ninguna IA generó fixes válidos ({len(ai_failures)} intento(s) fallidos)",
                "HEALTH_WARN",
                {"phase": "validation_fix", "failures": ai_failures},
            )
        return []

    @staticmethod
    def _parse_fixes(response: str) -> list[dict]:
        # Try direct JSON array
        try:
            data = json.loads(response)
            if isinstance(data, list):
                return [f for f in data if f.get("file") and f.get("code")]
            if isinstance(data, dict) and isinstance(data.get("fixes"), list):
                return [f for f in data["fixes"] if f.get("file") and f.get("code")]
        except (json.JSONDecodeError, TypeError):
            pass
        # Try JSON inside markdown fence
        for m in re.finditer(r"```(?:json)?\s*(\[.*?\])\s*```", response, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list):
                    return [f for f in data if f.get("file") and f.get("code")]
            except json.JSONDecodeError:
                continue
        # Try bare array in response
        m = re.search(r"\[\s*\{.*?\}\s*\]", response, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data, list):
                    return [f for f in data if f.get("file") and f.get("code")]
            except json.JSONDecodeError:
                pass
        return []

    # ---------------------------------------------------------- main loop

    async def validate_and_fix(
        self,
        source_dir: Path,
        install_cmd: str,
        run_cmd: str,
        project_description: str,
        workspace: Path = None,
        architecture: Optional[dict] = None,
    ) -> dict:
        """Setup env, run build, fix errors in a loop. Returns summary dict."""
        log_entries = []

        self.notify("Preparando entorno de ejecución...", "PHASE_START", {"phase": "validation"})

        # 1. Setup environment
        self.notify("Instalando dependencias del proyecto...", "LOG", {})
        setup_ok, setup_out = await self.setup_environment(source_dir, install_cmd, run_cmd)
        log_entries.append({"step": "setup", "ok": setup_ok, "output": setup_out[:500]})
        if not setup_ok:
            self.notify(f"Advertencia en setup: {setup_out[:200]}", "HEALTH_WARN", {"phase": "validation_setup", "reason": "setup_failed"})

        # 2. Detect build check command
        check_cmd = self.detect_check_command(source_dir, run_cmd, install_cmd)
        if not check_cmd:
            self.notify("Stack sin comando de validación disponible — omitiendo.", "LOG", {"phase": "validation", "reason": "no_check_command"})
            self._save_log(
                workspace or source_dir,
                log_entries,
                final_status="skipped",
                failed_modules=[],
                regeneration_recommended=False,
                error_summary="No hay comando de validación para este stack.",
            )
            return {"rounds": 0, "fixed": False, "skipped": True}

        cmd_str = " ".join(check_cmd)
        self.notify(f"Validando: {cmd_str}", "LOG", {})

        result = {
            "rounds": 0,
            "fixed": False,
            "errors_final": "",
            "failed_modules": [],
            "regeneration_recommended": False,
        }

        # 3. Build + fix loop
        for round_num in range(1, self.MAX_FIX_ROUNDS + 1):
            success, output = await self.run_build_check(source_dir, check_cmd)
            log_entries.append({"step": f"build_round_{round_num}", "ok": success, "output": output[:1000]})

            if success:
                self.notify(
                    f"Build exitoso en ronda {round_num} — sin errores.",
                    "CHECKPOINT",
                    {"phase": "validation", "round": round_num, "success": True},
                )
                result.update({"rounds": round_num, "fixed": True})
                self._save_log(
                    workspace or source_dir,
                    log_entries,
                    final_status="fixed",
                    failed_modules=[],
                    regeneration_recommended=False,
                    error_summary="Sin errores de build.",
                )
                return result

            self.notify(
                f"Ronda {round_num}/{self.MAX_FIX_ROUNDS} — errores detectados, solicitando correcciones...",
                "HEALTH_WARN",
                {"round": round_num, "errors": output[:400]},
            )
            print(f"\n  [VALID] Round {round_num} errors:\n{output[:600]}\n")

            fixes = await self._ask_for_fixes(source_dir, output, project_description, architecture=architecture)
            if not fixes:
                self.notify("IA no pudo generar correcciones para estos errores.", "LOG", {"phase": "validation_fix", "round": round_num, "reason": "no_ai_fixes"})
                failed_modules = self._extract_failed_modules(output, architecture)
                result.update({
                    "rounds": round_num,
                    "errors_final": output,
                    "failed_modules": failed_modules,
                    "regeneration_recommended": bool(failed_modules),
                })
                break

            applied = 0
            for fix in fixes:
                filepath = (fix.get("file") or "").strip().lstrip("/\\")
                code = fix.get("code", "")
                reason = fix.get("reason", "")
                if not filepath or not code:
                    continue
                # If AI returned an absolute path, try to make it relative to source_dir
                fp_path = Path(filepath)
                if fp_path.is_absolute():
                    try:
                        filepath = fp_path.relative_to(source_dir).as_posix()
                    except ValueError:
                        filepath = fp_path.name  # last resort: just the filename
                else:
                    filepath = filepath.replace("\\", "/")
                target = source_dir / filepath
                is_new_file = not target.exists()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(code, encoding="utf-8")
                if is_new_file:
                    print(f"    [FIX] WARNING: created new file (path may be wrong): {filepath}")
                self.notify(
                    f"[Ronda {round_num}] Corregido: {filepath}" + (f" — {reason}" if reason else ""),
                    "FILE_GENERATED",
                    {"filename": filepath, "code": code, "validated": False, "fix_round": round_num},
                )
                log_entries.append({"step": "fix", "round": round_num, "file": filepath, "reason": reason})
                applied += 1
                print(f"    [FIX] {filepath}" + (f": {reason}" if reason else ""))

            self.notify(
                f"Ronda {round_num}: {applied} corrección(es) aplicada(s). Revalidando...",
                "CHECKPOINT",
                {"phase": "validation", "round": round_num, "applied": applied},
            )

        # Final check after all rounds
        success, output = await self.run_build_check(source_dir, check_cmd)
        failed_modules = [] if success else self._extract_failed_modules(output, architecture)
        result.update({
            "rounds": self.MAX_FIX_ROUNDS,
            "fixed": success,
            "errors_final": "" if success else output,
            "failed_modules": failed_modules,
            "regeneration_recommended": (not success) and bool(failed_modules),
        })

        if success:
            self.notify("Build correcto tras correcciones automáticas.", "CHECKPOINT", {"phase": "validation", "success": True, "origin": "auto_fix"})
        else:
            self.notify(
                f"Build con errores pendientes tras {self.MAX_FIX_ROUNDS} rondas. Revisión manual recomendada.",
                "HEALTH_WARN",
                {"phase": "validation", "reason": "max_rounds_reached", "origin": "auto_fix", "errors": output[:300]},
            )

        self._save_log(
            workspace or source_dir,
            log_entries,
            final_status="fixed" if success else "failed",
            failed_modules=result.get("failed_modules", []),
            regeneration_recommended=result.get("regeneration_recommended", False),
            error_summary=self._summarize_errors(result.get("errors_final", "")),
        )
        return result

    # -------------------------------------------------------------- helpers

    async def _run(self, cmd: list[str], cwd: Path, timeout: int = None) -> tuple[int, str]:
        timeout = timeout or self.BUILD_TIMEOUT

        def _sync():
            try:
                if sys.platform == "win32":
                    r = subprocess.run(
                        subprocess.list2cmdline(cmd),
                        cwd=str(cwd), shell=True,
                        capture_output=True, text=True, timeout=timeout,
                    )
                else:
                    r = subprocess.run(
                        cmd, cwd=str(cwd),
                        capture_output=True, text=True, timeout=timeout,
                    )
                return r.returncode, (r.stdout + "\n" + r.stderr).strip()
            except subprocess.TimeoutExpired:
                return 1, f"Timeout after {timeout}s"
            except FileNotFoundError:
                return 1, f"Command not found: {cmd[0]}"
            except Exception as e:
                return 1, str(e)

        return await asyncio.to_thread(_sync)

    def _extract_failed_modules(self, error_output: str, architecture: Optional[dict]) -> list[str]:
        if not error_output or not architecture:
            return []

        modules = architecture.get("modulos", []) if isinstance(architecture, dict) else []
        if not isinstance(modules, list) or not modules:
            return []

        output_lower = error_output.lower()
        found = set()

        for mod in modules:
            name = str(mod.get("nombre", "")).strip()
            if not name:
                continue

            # Match explicit module mentions in compiler/runtime logs
            if re.search(rf"\b{re.escape(name.lower())}\b", output_lower):
                found.add(name)
                continue

            for rel in mod.get("archivos_principales", []) or []:
                rel_norm = str(rel).replace("\\", "/").lower().strip()
                if not rel_norm:
                    continue
                basename = rel_norm.split("/")[-1]
                if rel_norm in output_lower or basename in output_lower:
                    found.add(name)
                    break

        return sorted(found)

    @staticmethod
    def _summarize_errors(error_output: str) -> str:
        if not error_output:
            return ""
        lines = [ln.strip() for ln in error_output.splitlines() if ln.strip()]
        return " | ".join(lines[:3])

    def _save_log(
        self,
        workspace: Path,
        entries: list[dict],
        final_status: str = "unknown",
        failed_modules: Optional[list[str]] = None,
        regeneration_recommended: bool = False,
        error_summary: str = "",
    ) -> None:
        try:
            log = {
                "timestamp": datetime.now().isoformat(),
                "final_status": final_status,
                "rounds": entries,
                "failed_modules": failed_modules or [],
                "regeneration_recommended": regeneration_recommended,
                "error_summary": error_summary,
            }
            (workspace / "correction_log.json").write_text(
                json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass
