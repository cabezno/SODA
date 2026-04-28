"""PhaseMixin — post-DEV phase methods extracted from SodaOrchestrator.

Phases here run after the core DEV/VALIDATION loop. They reference only
`self.*` attributes and helpers defined on SodaOrchestrator, which is
available through MRO when the mixin is used via inheritance.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING, Optional

from kernel.audit.language_auditor import LanguageAuditor
from kernel.dependency_graph import DependencyGraph, ExecutionPlan
from kernel.design.design_context_injector import DesignContextInjector
from kernel.logging.error_reporter import fmt_response
from kernel.persistence.requirements_store import RequirementsStore
from kernel.validation.architecture_validator import ArchitectureValidator
from kernel.validation.blueprint_validator import BlueprintValidator

if TYPE_CHECKING:
    from kernel.orchestrator import Project


class PhaseMixin:
    """Mixin providing phase implementations for SodaOrchestrator.

    Covers pre-DEV pipeline phases (wisdom, capabilities, planning, design,
    verify, master_contract) and all post-DEV phases (audit, quality,
    visual, iteration, feedback, docs, evolution).
    """

    # ------------------------------------------------------------------ #
    # Phase: Wisdom (pre-DEV)                                              #
    # ------------------------------------------------------------------ #

    async def _phase_wisdom(self, project: Project) -> None:
        print("\n[FASE 0.5] Wisdom — analyzing description...")
        self._notify("Analizando descripción...", "PHASE_START", {"phase": "wisdom"})

        observations = await self.wisdom_agent.analyze(
            project.description,
            project.skills or [],
            project.profile or "",
            workspace=self._workspace(project),
        )
        if observations:
            for obs in observations:
                print(f"  [{obs.type.upper()}] {obs.message}")
                self._notify(obs.message, "WISDOM", {"type": obs.type, "suggestion": obs.suggestion})

        needs_answer = [o for o in observations if o.type in ("ambiguity", "missing_requirement")]
        print(f"  [OK] {len(observations)} observation(s)")

        clarifications = []
        for i, obs in enumerate(needs_answer):
            pregunta = (obs.suggestion.strip() or obs.message)[:200]
            total = len(needs_answer)
            label = f"[{i+1}/{total}] " if total > 1 else ""
            answer = await self.user_interaction.ask(
                f"{label}{pregunta}\n\n(Respondé con detalles o escribí 'saltar' para omitir...)",
                self._notify,
            )
            if answer and answer.strip().lower() not in ("skip", "saltar", "s", "omitir"):
                clarifications.append(answer.strip())

        if clarifications:
            project.description += "\n\nAclaraciones del usuario:\n" + "\n".join(f"- {c}" for c in clarifications)
            self._notify("Descripción enriquecida con tus respuestas.", "LOG")

        self._notify("Análisis de sabiduría completado.", "LOG")

    # ------------------------------------------------------------------ #
    # Phase: Capabilities (pre-DEV)                                        #
    # ------------------------------------------------------------------ #

    async def _phase_capabilities(self, project: Project) -> None:
        print("\n[FASE 0] Capabilities — matching skills and profile...")
        self._notify("Buscando skills y perfil...", "PHASE_START", {"phase": "capabilities"})
        from kernel.orchestrator import ProjectState
        project.state = ProjectState.CAPABILITIES

        try:
            skills = await self.skill_manager.select(project.description)
        except Exception as exc:
            self._notify(
                f"Skill matching falló (usando defaults): {type(exc).__name__}: {exc}",
                "HEALTH_WARN",
                {"phase": "capabilities", "error": str(exc)},
            )
            skills = []
        try:
            profile = await self.profile_manager.select(project.description, skills)
        except Exception as exc:
            self._notify(
                f"Profile matching falló (usando default): {type(exc).__name__}: {exc}",
                "HEALTH_WARN",
                {"phase": "capabilities", "error": str(exc)},
            )
            profile = "profile_general_dev"

        project.skills = skills
        project.profile = profile

        print(f"  [OK] Skills: {skills}")
        print(f"  [OK] Profile: {profile}")
        self._notify(
            f"Perfil: {profile} | Skills: {', '.join(skills) or 'ninguno'}",
            "CAPABILITIES",
            {"skills": skills, "profile": profile},
        )

        cap_sug = await self.copilot_consultant.review_capabilities(skills, profile, project.description)
        cap_handled = self._handle_copilot_review(cap_sug, "capabilities")
        if cap_handled["applied"]:
            numbered = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(cap_handled["changes"]))
            project.description += f"\n\nSUGERENCIA COPILOT (capabilities):\n{numbered}"

        self._save_state(project)

    # ------------------------------------------------------------------ #
    # Phase: Planning (pre-DEV)                                            #
    # ------------------------------------------------------------------ #

    async def _phase_planning(self, project: Project) -> ExecutionPlan:
        from kernel.orchestrator import ProjectState
        print("\n[FASE 3] Planning — building module DAG...")
        self._notify("Construyendo plan de ejecución...", "PHASE_START", {"phase": "planning"})
        project.state = ProjectState.PLANNING

        # Prefer master_contract.json (typed, snake_case IDs) over legacy architecture.json.
        # If master_contract exists, derive a DependencyGraph-compatible modulos list from it.
        modulos = self._resolve_modulos_for_planning(project)
        if not modulos:
            raise ValueError("Architecture has no modules defined.")
        graph = DependencyGraph(modulos)
        plan = graph.build_execution_plan()
        if plan.broken_edges:
            self._notify(
                f"Dependencias circulares detectadas y resueltas: {plan.broken_edges}",
                "HEALTH_WARN",
                {"broken_edges": [list(e) for e in plan.broken_edges]},
            )
        plan_data = {"levels": plan.levels, "order": plan.order, "parallelizable": plan.parallelizable}
        out = self._workspace(project) / "execution_plan.json"
        out.write_text(json.dumps(plan_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(graph.summary())
        print(f"  [OK] Plan -> {out}")
        total_files = sum(
            len(m.get("archivos_principales", []))
            for m in modulos
            if m["nombre"] in {n for level in plan.levels for n in level}
        )
        plan_sug = await self.copilot_consultant.review_plan(plan.levels, project.architecture)
        plan_handled = self._handle_copilot_review(plan_sug, "planning")
        if plan_handled["applied"]:
            project.architecture["_planning_copilot_note"] = plan_handled["notes"]

        self._notify("Plan listo.", "CHECKPOINT", {
            "number": 3,
            "project_id": project.id,
            "levels": plan.levels,
            "total_modules": sum(len(l) for l in plan.levels),
            "total_files": total_files,
        })
        self._save_state(project)

        # Pre-create venv now so it's ready before DEV starts generating files
        try:
            from kernel.sandbox.dynamic_env import DynamicEnvironment
            _pre_env = DynamicEnvironment(project.id, self._workspace(project), self._notify)
            asyncio.create_task(_pre_env.ensure_venv())
        except Exception:
            pass

        return plan

    def _resolve_modulos_for_planning(self, project: Project) -> list[dict]:
        """Return the module list for DependencyGraph.

        Priority:
          1. master_contract.json (snake_case IDs, guaranteed DAG)
          2. topology.json (from Gemini, validated IDs)
          3. project.architecture (legacy format, campo 'nombre')
        """
        # Try master_contract in memory first, then on disk
        contract_path = self._workspace(project) / "master_contract.json"
        if contract_path.exists():
            try:
                import json as _json
                raw = _json.loads(contract_path.read_text(encoding="utf-8"))
                mc_modules = raw.get("modules", [])
                if mc_modules:
                    # Convert to DependencyGraph format: nombre + dependencias
                    return [
                        {
                            "nombre": m["id"],
                            "responsabilidad": m.get("purpose", ""),
                            "archivos_principales": m.get("archivos_principales", []),
                            "dependencias": m.get("depends_on", []),
                            "endpoints": [],
                        }
                        for m in mc_modules
                        if isinstance(m, dict) and m.get("id")
                    ]
            except Exception as exc:
                self._notify(f"No se pudo leer master_contract.json para planning: {exc}", "LOG", {})

        # Fallback: topology.json
        topology = getattr(project, "topology", None)
        if not topology:
            topo_path = self._workspace(project) / "topology.json"
            if topo_path.exists():
                try:
                    import json as _json
                    topology = _json.loads(topo_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
        if topology and topology.get("modulos"):
            return [
                {
                    "nombre": m["id"],
                    "responsabilidad": m.get("responsabilidad", ""),
                    "archivos_principales": m.get("archivos_principales", []),
                    "dependencias": m.get("depende_de_ids", []),
                    "endpoints": [],
                }
                for m in topology["modulos"]
                if isinstance(m, dict) and m.get("id")
            ]

        # Last resort: legacy architecture.json format
        return project.architecture.get("modulos", []) if project.architecture else []

    # ------------------------------------------------------------------ #
    # Phase: Design (pre-DEV)                                              #
    # ------------------------------------------------------------------ #

    async def _phase_design(self, project: Project) -> None:
        """FASE 3.5 — Generate design_spec.json for frontend projects (between PLAN and DEV)."""
        self._notify("Generando especificación de diseño UI...", "PHASE_START", {"phase": "design"})
        workspace = self._workspace(project)
        try:
            spec = self.ui_design_agent.generate_spec(project.blueprint, project.architecture)
            self.ui_design_agent.save_spec(spec, workspace)
            self._notify(
                f"Diseño generado: {spec.design_system}, {spec.layout_pattern}, dark={spec.dark_mode}",
                "PHASE_DONE",
                {"phase": "design", "design_system": spec.design_system, "layout": spec.layout_pattern},
            )
            print(f"  [OK] Design spec → {workspace / 'design_spec.json'}")
        except Exception as exc:
            self._notify(f"UIDesignAgent falló (no crítico): {exc}", "LOG", {})
            print(f"  [WARN] UIDesignAgent failed: {exc}")

    # ------------------------------------------------------------------ #
    # Phase: Verify conformance (post-DEV)                                 #
    # ------------------------------------------------------------------ #

    async def _phase_verify(self, project: Project) -> None:
        """Architectural conformance check: Haiku verifies every generated module
        against its contract and fixes non-conformances in place. Non-fatal."""
        try:
            source_dir = self._workspace(project) / "source"
            self._notify(
                "Verificando conformidad arquitectónica con Haiku...",
                "PHASE_START",
                {"phase": "conformance_verify"},
            )
            # PASO 1: pass topology + master_contract as ground truth for file paths and typed interfaces
            _topology = getattr(project, "topology", None) or {}
            _master_contract = None
            _mc_path = self._workspace(project) / "master_contract.json"
            if _mc_path.exists():
                try:
                    import json as _json
                    _master_contract = _json.loads(_mc_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            await self.conformance_verifier.verify_project(
                project.architecture, source_dir,
                master_contract=_master_contract,
                topology=_topology,
            )
            self._notify(
                "Verificación de conformidad completa.",
                "PHASE_DONE",
                {"phase": "conformance_verify"},
            )
        except Exception as exc:
            import traceback as _tb
            print(f"  [VERIFY] Error (no crítico): {exc}")
            self._notify(
                f"ConformanceVerifier falló (no crítico): {type(exc).__name__}: {exc}",
                "HEALTH_WARN",
                {
                    "phase": "conformance_verify",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    "traceback": _tb.format_exc()[-1500:],
                },
            )

    # ------------------------------------------------------------------ #
    # Phase: Master contract (parallel to legacy arch)                     #
    # ------------------------------------------------------------------ #

    async def _phase_master_contract(self, project: Project) -> None:
        """Generate master_contract.json — Claude (3 attempts) → Gemini fallback (2 attempts).

        All errors are reported to console and UI. If both fail, the user is
        notified with a full summary. The pipeline continues with architecture.json
        (legacy) in all failure cases.
        """
        try:
            from kernel.intelligence.complexity_classifier import ProjectComplexityClassifier
            from kernel.intelligence.architect import Architect, GeminiArchitect
            from kernel.integrity.contract_auditor import ContractAuditor
            from kernel.orchestration.contract_refinement_loop import ContractRefinementLoop

            self._notify(
                "Arquitecto v2: clasificando complejidad del proyecto...",
                "LOG",
                {"phase": "master_contract"},
            )
            classifier = ProjectComplexityClassifier()
            assessment = classifier.classify(project.blueprint)
            self._notify(
                f"Arquitecto v2: proyecto clasificado como '{assessment.level.value}' "
                f"(score {assessment.score}). {assessment.reasoning.splitlines()[0]}",
                "LOG",
                {"complexity": assessment.level.value, "score": assessment.score},
            )
            print(f"  [ARCH-V2] Complejidad: {assessment.level.value}")



            goal_tree = self._build_goal_tree_from_blueprint(project.blueprint)
            goal_tree_size = len(goal_tree.get("children", []))
            self._notify(
                f"Arquitecto v2: árbol de objetivos derivado del blueprint ({goal_tree_size} objetivo(s)).",
                "LOG",
                {"phase": "master_contract", "goal_count": goal_tree_size},
            )

            # topology.json is the new source of truth — pass it to Claude and the auditor
            topology = getattr(project, "topology", None) or {}

            active_skills = [
                {"name": s} if isinstance(s, str) else s
                for s in (project.skills or [])
            ]
            auditor = ContractAuditor(goal_tree=goal_tree, topology=topology)
            execute_kwargs = dict(
                blueprint=project.blueprint,
                complexity=assessment.level,
                topology=topology,
                active_skills=active_skills,
                active_profile={},
                goal_tree=goal_tree,
            )

            # ── Fase 1: Claude (3 intentos) ──────────────────────────────
            self._notify("Arquitecto v2: generando contrato con Claude (3 intentos)...", "LOG",
                         {"phase": "master_contract", "driver": "claude"})
            print("  [ARCH-V2] Claude: iniciando (3 intentos)...")
            claude_result = await ContractRefinementLoop(
                architect=Architect(self.claude),
                auditor=auditor,
                max_attempts=3,
                notify_fn=self._notify,
            ).execute(**execute_kwargs)

            if claude_result.status in ("approved", "approved_with_warnings"):
                self._save_master_contract(project, claude_result, assessment)
                return

            # Claude falló — loguear resumen claro
            claude_errors = len(claude_result.final_issues.all_errors) if claude_result.final_issues else 0
            claude_fail_msg = (
                f"Arquitecto v2 [Claude]: falló tras {len(claude_result.attempts)} intento(s). "
                f"{claude_errors} error(s) de auditoría. "
                + (f"Último error: {claude_result.failed_reason}" if claude_result.failed_reason else "Contrato no pasó auditoría.")
            )
            self._notify(claude_fail_msg, "HEALTH_WARN",
                         {"phase": "master_contract", "driver": "claude",
                          "attempts": len(claude_result.attempts),
                          "audit_errors": claude_errors,
                          "failed_reason": claude_result.failed_reason})
            print(f"  [ARCH-V2] Claude falló: {claude_result.failed_reason or f'{claude_errors} errores de auditoría'}")

            # ── Fase 2: Gemini fallback (2 intentos) ─────────────────────
            self._notify("Arquitecto v2: escalando a Gemini (2 intentos)...", "LOG",
                         {"phase": "master_contract", "driver": "gemini"})
            print("  [ARCH-V2] Gemini: iniciando fallback (2 intentos)...")
            gemini_result = await ContractRefinementLoop(
                architect=GeminiArchitect(self.gemini),
                auditor=auditor,
                max_attempts=2,
                notify_fn=self._notify,
            ).execute(**execute_kwargs)

            if gemini_result.status in ("approved", "approved_with_warnings"):
                self._save_master_contract(project, gemini_result, assessment)
                return

            # Gemini también falló — notificar al usuario con resumen completo
            gemini_errors = len(gemini_result.final_issues.all_errors) if gemini_result.final_issues else 0
            gemini_fail_msg = (
                f"Arquitecto v2 [Gemini]: falló tras {len(gemini_result.attempts)} intento(s). "
                f"{gemini_errors} error(s) de auditoría. "
                + (f"Último error: {gemini_result.failed_reason}" if gemini_result.failed_reason else "Contrato no pasó auditoría.")
            )
            self._notify(gemini_fail_msg, "HEALTH_WARN",
                         {"phase": "master_contract", "driver": "gemini",
                          "attempts": len(gemini_result.attempts),
                          "audit_errors": gemini_errors,
                          "failed_reason": gemini_result.failed_reason})

            # Resumen final para el usuario
            self.perf_tracker.record_contract_result(status="requires_user_intervention",
                                                      attempts=len(claude_result.attempts) + len(gemini_result.attempts))
            summary = (
                f"⚠️ Arquitecto v2: ni Claude ni Gemini pudieron generar el contrato maestro. "
                f"Claude: {claude_result.failed_reason or f'{claude_errors} errores de auditoría'}. "
                f"Gemini: {gemini_result.failed_reason or f'{gemini_errors} errores de auditoría'}. "
                f"Pipeline continúa con architecture.json (legacy)."
            )
            self._notify(summary, "HEALTH_WARN",
                         {"phase": "master_contract", "status": "both_failed",
                          "claude_reason": claude_result.failed_reason,
                          "gemini_reason": gemini_result.failed_reason})
            print(f"  [ARCH-V2] AMBOS FALLARON — legacy arch en uso.")
            print(f"  [ARCH-V2] Claude: {claude_result.failed_reason or f'{claude_errors} audit errors'}")
            print(f"  [ARCH-V2] Gemini: {gemini_result.failed_reason or f'{gemini_errors} audit errors'}")

        except Exception as exc:
            import traceback as _tb
            self._notify(
                f"Arquitecto v2 (non-fatal): {type(exc).__name__}: {exc}",
                "HEALTH_WARN",
                {"phase": "master_contract", "error": str(exc),
                 "error_type": type(exc).__name__,
                 "traceback": _tb.format_exc()[-1500:]},
            )
            print(f"  [ARCH-V2] Error inesperado: {type(exc).__name__}: {exc}")

    def _save_master_contract(self, project: Project, result, assessment) -> None:
        """Persist an approved master contract and emit success notifications."""
        from kernel.orchestration.contract_refinement_loop import ContractResult
        contract_path = self._workspace(project) / "master_contract.json"
        contract_path.write_text(result.contract.model_dump_json(indent=2), encoding="utf-8")
        attempt_count = len(result.attempts)
        driver_tag = "gemini-fallback" if "gemini" in result.contract.model_used else "claude"
        self.perf_tracker.record_contract_result(
            status=result.status,
            attempts=attempt_count,
            model=result.contract.model_used,
        )
        self._notify(
            f"Arquitecto v2: contrato maestro aprobado vía {driver_tag} "
            f"(status={result.status}, intentos={attempt_count}).",
            "LOG",
            {"phase": "master_contract", "status": result.status,
             "attempts": attempt_count, "driver": driver_tag,
             "complexity": assessment.level.value, "path": str(contract_path)},
        )
        print(f"  [ARCH-V2] master_contract.json -> {contract_path} (vía {driver_tag})")
        self._git_commit(
            project,
            f"feat: master contract approved via {driver_tag} "
            f"(complexity: {assessment.level.value}, attempts: {attempt_count})",
        )
        if result.status == "approved_with_warnings":
            warning_count = len(result.attempts[-1].audit_report.all_warnings)
            self._notify(
                f"Arquitecto v2: {warning_count} warning(s) en el contrato maestro.",
                "HEALTH_WARN",
                {"warnings": [w.description for w in result.attempts[-1].audit_report.all_warnings]},
            )

    # ------------------------------------------------------------------ #
    # Phase: Audit                                                         #
    # ------------------------------------------------------------------ #

    async def _phase_audit(self, project: Project) -> None:
        """Language-aware audit: check generated code against stack rules, fix with AI if needed."""
        print("\n[FASE 4.2] Audit — language rules check...")
        self._notify("Auditando código generado...", "PHASE_START", {"phase": "audit"})

        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            self._notify("Sin directorio source — auditoría omitida.", "LOG", {})
            return

        auditor = LanguageAuditor(
            claude_driver=self.claude,
            gemini_driver=self.gemini,
            context_builder=self.builder,
            notify_fn=self._notify,
        )

        audit_result = auditor.audit_project(source_dir, project.architecture, project.blueprint)

        if not audit_result.violations:
            self._notify("Auditoría: sin problemas.", "CHECKPOINT", {"phase": "audit", "score": 100})
            return

        if audit_result.errors:
            fixes = await auditor.request_ai_fix(
                audit_result, source_dir, project.description, project.architecture
            )
            applied = 0
            for fix in fixes:
                filepath = (fix.get("file") or "").strip().lstrip("/\\")
                code = fix.get("code", "")
                reason = fix.get("reason", "")
                if not filepath or not code:
                    continue
                target = source_dir / filepath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(code, encoding="utf-8")
                self._notify(
                    f"[Audit] Corregido: {filepath}" + (f" — {reason}" if reason else ""),
                    "FILE_GENERATED",
                    {"filename": filepath, "code": code, "validated": False, "audit_fix": True},
                )
                applied += 1

            if applied:
                self._notify(
                    f"Auditoría: {applied} archivo(s) corregido(s) por IA.",
                    "CHECKPOINT",
                    {"phase": "audit", "applied": applied, "score": audit_result.score},
                )
            else:
                self._notify(
                    f"Auditoría: {len(audit_result.errors)} error(es) sin corrección automática — "
                    "se intentará en la fase de validación.",
                    "HEALTH_WARN",
                    {"phase": "audit", "violations": [v.to_dict() for v in audit_result.errors]},
                )

        try:
            report_path = self._workspace(project) / "audit_report.json"
            report_path.write_text(
                json.dumps(audit_result.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Phase: Import validation                                             #
    # ------------------------------------------------------------------ #

    async def _phase_import_validation(self, project: Project) -> None:
        self._notify("Validando dependencias del manifiesto…", "PHASE_START", {"phase": "import_validation"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = self.import_validator.validate(source_dir, project.architecture)
            self._save_phase_report(project, "import_validation_report.json", report.to_dict())
        except Exception as e:
            self._notify(f"ImportValidator falló (no crítico): {e}", "LOG", {})

    # ------------------------------------------------------------------ #
    # Phase: Security review                                               #
    # ------------------------------------------------------------------ #

    async def _phase_security_review(self, project: Project) -> None:
        self._notify("Revisando seguridad del código generado…", "PHASE_START", {"phase": "security_review"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = self.security_reviewer.review(source_dir, project.blueprint)
            self._save_phase_report(project, "security_report.json", report.to_dict())
            if not report.passed and (report.critical or report.high):
                await self.security_reviewer.request_ai_suggestions(report, source_dir)
        except Exception as e:
            self._notify(f"SecurityReviewer falló (no crítico): {e}", "LOG", {})

    # ------------------------------------------------------------------ #
    # Phase: Test generation                                               #
    # ------------------------------------------------------------------ #

    async def _phase_test_generation(self, project: Project) -> None:
        import json as _json
        self._notify("Generando tests automáticos…", "PHASE_START", {"phase": "test_generation"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            # Load master_contract for contract-based test generation
            master_contract: dict | None = None
            mc_path = self._workspace(project) / "master_contract.json"
            if mc_path.exists():
                try:
                    master_contract = _json.loads(mc_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

            module_generated_code: dict[str, dict[str, str]] = {}
            for mod in project.architecture.get("modulos", []):
                nombre = mod.get("nombre", "")
                mod_id = mod.get("id") or nombre
                files: dict[str, str] = {}
                for fp in mod.get("archivos_principales", []):
                    fpath = source_dir / fp
                    if fpath.exists():
                        try:
                            files[fp] = fpath.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass
                if files:
                    module_generated_code[nombre] = files
                    if mod_id != nombre:
                        module_generated_code[mod_id] = files

            report = await self.test_generator.generate_for_project(
                source_dir,
                project.architecture,
                project.blueprint,
                module_generated_code,
                master_contract=master_contract,
            )
            self._save_phase_report(project, "test_generation_report.json", report.to_dict())

            # Functional E2E tests from blueprint funcionalidades
            if hasattr(self, "functional_test_generator") and self.functional_test_generator:
                try:
                    await self.functional_test_generator.generate(
                        source_dir,
                        project.blueprint,
                        project.architecture,
                    )
                except Exception as e_e2e:
                    self._notify(f"FunctionalTestGenerator falló (no crítico): {e_e2e}", "LOG", {})

            self._git_commit(project, "Fase 4.3: Tests automáticos generados (contract-based + E2E)")
        except Exception as e:
            self._notify(f"TestGenerator falló (no crítico): {e}", "LOG", {})

    # ------------------------------------------------------------------ #
    # Phase: API contract                                                  #
    # ------------------------------------------------------------------ #

    async def _phase_api_contract(self, project: Project) -> None:
        self._notify("Verificando contrato API frontend↔backend…", "PHASE_START", {"phase": "api_contract"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = self.api_enforcer.enforce(source_dir, project.architecture, project.blueprint)
            self._save_phase_report(project, "api_contract_report.json", report.to_dict())
        except Exception as e:
            self._notify(f"APIContractEnforcer falló (no crítico): {e}", "LOG", {})

    # ------------------------------------------------------------------ #
    # Phase: Run tests + triage failures                                   #
    # ------------------------------------------------------------------ #

    async def _phase_run_and_triage_tests(self, project: Project) -> None:
        """Run generated test suite, triage failures, auto-fix bad code or regenerate bad tests."""
        import asyncio
        import json as _json
        from kernel.testing.test_triage import triage_failures, TriageVerdict
        from kernel.agents.auto_fix_agent import AutoFixAgent

        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return

        # Detect framework + run command
        test_report_path = self._workspace(project) / "test_generation_report.json"
        if not test_report_path.exists():
            return
        try:
            test_report = _json.loads(test_report_path.read_text(encoding="utf-8"))
        except Exception:
            return

        framework = test_report.get("framework", "pytest")
        generated_files = test_report.get("generated_modules", [])
        if not generated_files:
            return

        if framework == "pytest":
            cmd = ["python", "-m", "pytest", "tests/", "--tb=short", "-q", "--no-header"]
        elif framework == "jest":
            cmd = ["npm", "test", "--", "--passWithNoTests"]
        elif framework == "go_test":
            cmd = ["go", "test", "./..."]
        else:
            return  # unsupported runner

        self._notify(
            f"TestRunner: ejecutando suite [{framework}]…",
            "PHASE_START",
            {"phase": "test_run", "framework": framework},
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(source_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            combined = (stdout or b"").decode("utf-8", errors="replace") + "\n" + (stderr or b"").decode("utf-8", errors="replace")
            exit_code = proc.returncode
        except asyncio.TimeoutError:
            self._notify("TestRunner: timeout al ejecutar tests — omitiendo triage.", "HEALTH_WARN", {})
            return
        except Exception as exc:
            self._notify(f"TestRunner: no se pudo ejecutar [{framework}]: {exc}", "LOG", {})
            return

        self._notify(
            f"TestRunner: exit_code={exit_code}",
            "LOG",
            {"phase": "test_run", "exit_code": exit_code, "output_snippet": combined[-500:]},
        )

        if exit_code == 0:
            self._notify("TestRunner: todos los tests pasaron.", "CHECKPOINT", {"phase": "test_run"})
            self._save_phase_report(project, "test_run_report.json", {"framework": framework, "passed": True, "failures": []})
            return

        # Parse failures — use combined output as a single failure block for triage
        failures = [{"output": combined, "test_file": ""}]
        triage_report = triage_failures(failures, source_dir)
        self._save_phase_report(project, "test_run_report.json", {
            "framework": framework,
            "passed": False,
            "triage": triage_report.to_dict(),
        })

        # Load master_contract for auto-fixer context
        master_contract: dict | None = None
        mc_path = self._workspace(project) / "master_contract.json"
        if mc_path.exists():
            try:
                master_contract = _json.loads(mc_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        for result in triage_report.results:
            if result.verdict == TriageVerdict.BAD_CODE and result.source_files:
                self._notify(
                    f"Triage: código fuente incorrecto — auto-fix en {result.source_files}",
                    "HEALTH_WARN",
                    {"phase": "test_triage", "verdict": "bad_code", "files": result.source_files},
                )
                fixer = AutoFixAgent(
                    claude_driver=getattr(self, "claude", None),
                    gemini_driver=getattr(self, "gemini", None),
                    context_builder=getattr(self, "builder", None),
                    notify_fn=self._notify,
                )
                await fixer.fix_files_from_errors(
                    errors=[{"file": f, "message": combined[-800:]} for f in result.source_files],
                    raw_stderr=combined,
                    source_dir=source_dir,
                    master_contract=master_contract,
                    workspace_path=self._workspace(project),
                )

            elif result.verdict == TriageVerdict.BAD_TEST and result.test_file:
                self._notify(
                    f"Triage: test incorrecto — regenerando {result.test_file}",
                    "HEALTH_WARN",
                    {"phase": "test_triage", "verdict": "bad_test", "file": result.test_file},
                )
                # Identify which module this test file belongs to
                mod_id = Path(result.test_file).stem.removeprefix("test_")
                target_mod = next(
                    (m for m in project.architecture.get("modulos", [])
                     if (m.get("id") or m.get("nombre", "")) == mod_id),
                    None,
                )
                if target_mod:
                    src_files = {
                        fp: (source_dir / fp).read_text(encoding="utf-8", errors="ignore")
                        for fp in target_mod.get("archivos_principales", [])
                        if (source_dir / fp).exists()
                    }
                    if src_files:
                        try:
                            new_content = await self.test_generator._generate_test_file(
                                target_mod, src_files, framework, project.blueprint, typed_module=None
                            )
                            if new_content and len(new_content.strip()) > 50:
                                out = source_dir / result.test_file
                                out.write_text(new_content, encoding="utf-8")
                                self._notify(
                                    f"Triage: test regenerado → {result.test_file}",
                                    "FILE_GENERATED",
                                    {"filename": result.test_file, "code": new_content, "validated": False, "phase": "test_triage"},
                                )
                        except Exception as exc:
                            self._notify(f"Triage: no se pudo regenerar {result.test_file}: {exc}", "LOG", {})

    # ------------------------------------------------------------------ #
    # Phase: Boot agent                                                    #
    # ------------------------------------------------------------------ #

    async def _phase_boot_agent(self, project: Project) -> None:
        self._notify("BootAgent: instalando y arrancando proyecto…", "PHASE_START", {"phase": "boot_agent"})
        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return
        try:
            report = await self.boot_agent.run(source_dir, project.architecture, project.blueprint)
            self._save_phase_report(project, "boot_report.json", report.to_dict())
            if report.final_ok:
                self._git_commit(project, "Fase 5.1: Proyecto arranca correctamente")
        except Exception as e:
            self._notify(f"BootAgent falló (no crítico): {e}", "LOG", {})

    # ------------------------------------------------------------------ #
    # Phase: Setup and verify                                              #
    # ------------------------------------------------------------------ #

    async def _phase_setup_and_verify(self, project: Project) -> dict:
        """Install dependencies, launch project, basic smoke, then full endpoint smoke suite."""
        run_command = self._get_run_command(project)
        install_command = self._get_install_command(project)
        if not run_command:
            return {}
        workspace = self._workspace(project)

        # If BootAgent already ran a successful install in this pipeline run, skip reinstall
        # to avoid running the same package manager twice on identical deps.
        effective_install = install_command
        boot_report_path = workspace / "boot_report.json"
        if install_command and boot_report_path.exists():
            try:
                import json as _json
                boot_data = _json.loads(boot_report_path.read_text(encoding="utf-8"))
                if not boot_data.get("skipped", True) and boot_data.get("attempts", 0) > 0:
                    effective_install = ""
                    self._notify(
                        "BootAgent ya instaló dependencias — omitiendo reinstalación.",
                        "LOG",
                        {"phase": "setup", "reason": "boot_install_reused"},
                    )
            except Exception:
                pass

        self._notify("Configurando y verificando proyecto generado…", "LOG", {"phase": "setup"})
        result = await self.project_runner.setup_and_verify(
            project_workspace=workspace,
            run_command=run_command,
            install_command=effective_install,
            notify_fn=self._notify,
        )
        smoke_basic = result.get("smoke", {})
        base_url = smoke_basic.get("target_url", "")
        if base_url and smoke_basic.get("passed"):
            source_dir = workspace / "source"
            arch = project.architecture or {}
            self._notify(f"Ejecutando smoke suite de endpoints en {base_url}…", "LOG", {"phase": "smoke_suite"})
            suite = await self.smoke_tester.run_suite_async(base_url, arch, source_dir if source_dir.exists() else None)
            result["smoke_suite"] = suite.to_dict()
            if not suite.all_passed:
                self._notify(
                    f"Smoke suite: {suite.passed}/{suite.total} endpoints OK",
                    "HEALTH_WARN",
                    {"phase": "smoke_suite", **suite.to_dict()},
                )
            else:
                self._notify(f"Smoke suite: {suite.total} endpoints OK", "LOG", {"phase": "smoke_suite"})
        return result

    # ------------------------------------------------------------------ #
    # Phase: Targeted regeneration                                         #
    # ------------------------------------------------------------------ #

    async def _phase_targeted_regeneration(self, project: Project, module_names: list[str], errors_final: str = "") -> None:
        modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}
        source_dir = self._workspace(project) / "source"
        note = "\n\nREGENERACIÓN AUTOMÁTICA POR FALLO DE VALIDACIÓN"
        if errors_final:
            note += f"\nResumen de errores:\n{errors_final[:1000]}"

        self._notify(
            f"Regeneración dirigida iniciada para {len(module_names)} módulo(s).",
            "PHASE_START",
            {"phase": "targeted_regeneration", "modules": module_names},
        )

        skills_context: Optional[str] = None
        profile_context: Optional[str] = None
        try:
            if project.skills:
                skills_context = self.skill_manager.load_context(project.skills, role="code_generator") or None
            if project.profile:
                profile_context = self.profile_manager.load_context(project.profile) or None
        except Exception:
            pass

        dependency_context: dict = {}
        if source_dir.exists():
            for mod in project.architecture.get("modulos", []):
                mod_nombre = mod.get("nombre", "")
                if mod_nombre in module_names:
                    continue
                files: dict[str, str] = {}
                for fp in mod.get("archivos_principales", []):
                    fpath = source_dir / fp
                    if fpath.exists():
                        try:
                            files[fp] = fpath.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass
                if files:
                    dependency_context[mod_nombre] = files

        user_requirements = RequirementsStore(project.workspace).as_task_field()
        for nombre in module_names:
            if nombre not in modulos_by_name:
                continue

            original = modulos_by_name[nombre]
            module = {
                **original,
                "responsabilidad": f"{original.get('responsabilidad', '').rstrip()}{note}",
            }
            self._notify(f"Regenerando: {nombre}", "MODULE_START", {"module": nombre})
            generated_files = await self.code_gen.generate_module(
                module, project.blueprint, project.architecture,
                user_requirements=user_requirements,
                dependency_context=dependency_context,
                skills_context=skills_context,
                profile_context=profile_context,
            )
            for gf in generated_files:
                out = source_dir / gf.filepath
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(gf.content, encoding="utf-8", errors="replace")
                self._notify(
                    f"Actualizado: {gf.filepath}",
                    "FILE_GENERATED",
                    {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                )
            self._notify(f"Módulo regenerado: {nombre}", "MODULE_DONE", {"module": nombre})

        self._save_state(project)

    # ------------------------------------------------------------------ #
    # Phase: Visual inspection                                             #
    # ------------------------------------------------------------------ #

    def _find_visual_modules(self, project: Project, issues: list[str]) -> list[str]:
        """Return module names likely responsible for detected visual issues."""
        ui_keywords = {"frontend", "ui", "view", "template", "page", "render", "html", "css", "react", "vue", "svelte", "static"}
        modulos = project.architecture.get("modulos", [])
        candidates = []
        for mod in modulos:
            nombre = mod.get("nombre", "").lower()
            resp = mod.get("responsabilidad", "").lower()
            if any(kw in nombre or kw in resp for kw in ui_keywords):
                candidates.append(mod["nombre"])
        if not candidates and modulos:
            candidates = [modulos[0]["nombre"]]
        return candidates

    async def _phase_visual_inspection(self, project: Project, max_fix_iterations: int = 2) -> None:
        """Capture screenshot of running app, analyze with Gemini Flash vision, and regenerate UI modules if issues found."""
        run_command = self._get_run_command(project)
        install_command = self._get_install_command(project)
        if not run_command:
            return
        stack = self.project_runner.detect_stack(run_command, install_command)
        url = self.project_runner.infer_runtime_url(run_command, stack)
        if not url:
            return

        workspace = self._workspace(project)
        source_dir = workspace / "source"
        screenshot_dir = workspace / "_screenshots"
        context = f"Project: {project.id}. Stack: {stack}. URL: {url}"

        for iteration in range(1 + max_fix_iterations):
            screenshot_path = screenshot_dir / f"main_v{iteration}.png"
            self._notify(
                f"Visual Inspector: capturando screenshot (iteración {iteration + 1})…",
                "LOG", {"phase": "visual_inspection", "iteration": iteration + 1},
            )
            capture = await self.vision_capturer.capture_url(url, screenshot_path)
            if not capture.exists:
                self._notify(
                    f"Screenshot no disponible ({capture.error or 'app no corriendo'})",
                    "LOG", {},
                )
                return

            self._notify("Visual Inspector: analizando renderizado con Gemini Flash…", "LOG", {})
            inspection = await self.visual_inspector.analyze(screenshot_path, context=context)

            if not inspection.issues_detected:
                self._notify(
                    f"Visual Inspector: app renderiza correctamente. {inspection.ai_analysis}",
                    "LOG",
                    {"phase": "visual_inspection", "renders_correctly": True, "iteration": iteration + 1},
                )
                return

            self._notify(
                f"Visual Inspector detectó {len(inspection.issues_detected)} problema(s): "
                + "; ".join(inspection.issues_detected[:3]),
                "HEALTH_WARN",
                {
                    "phase": "visual_inspection",
                    "renders_correctly": inspection.renders_correctly,
                    "issues": inspection.issues_detected,
                    "suggestions": inspection.suggestions,
                    "summary": inspection.ai_analysis,
                    "iteration": iteration + 1,
                },
            )

            if iteration >= max_fix_iterations:
                break

            ui_modules = self._find_visual_modules(project, inspection.issues_detected)
            if not ui_modules:
                break

            issues_text = "\n".join(f"- {i}" for i in inspection.issues_detected[:6])
            suggestions_text = "\n".join(f"- {s}" for s in inspection.suggestions[:4])
            fix_note = (
                f"\n\nREGENERACIÓN POR PROBLEMAS VISUALES DETECTADOS (iteración {iteration + 1})\n"
                f"Problemas:\n{issues_text}\n"
                f"Sugerencias:\n{suggestions_text}"
            )

            modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}
            self._notify(
                f"Regenerando {len(ui_modules)} módulo(s) de UI por problemas visuales…",
                "PHASE_START",
                {"phase": "visual_fix", "modules": ui_modules, "iteration": iteration + 1},
            )
            for nombre in ui_modules:
                if nombre not in modulos_by_name:
                    continue
                original = modulos_by_name[nombre]
                module = {**original, "responsabilidad": original.get("responsabilidad", "").rstrip() + fix_note}
                generated_files = await self.code_gen.generate_module(
                    module, project.blueprint, project.architecture,
                    user_requirements=RequirementsStore(project.workspace).as_task_field(),
                )
                for gf in generated_files:
                    out = source_dir / gf.filepath
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(gf.content, encoding="utf-8", errors="replace")
                    self._notify(
                        f"Actualizado (visual fix): {gf.filepath}",
                        "FILE_GENERATED",
                        {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                    )
                self._notify(f"Módulo visual regenerado: {nombre}", "MODULE_DONE", {"module": nombre})

            self._save_state(project)

    # ------------------------------------------------------------------ #
    # Phase: Iteration (user feedback)                                     #
    # ------------------------------------------------------------------ #

    async def _phase_iteration(self, project: Project, user_request: str) -> None:
        """Re-generate modules affected by user feedback, then re-validate."""
        self._notify("Analizando cambios solicitados...", "PHASE_START", {"phase": "modification"})
        modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}

        affected: set = set()
        try:
            plan = await self.goal_interpreter.interpret(user_request, project.architecture, project.blueprint)
            report = await self.impact_analyzer.analyze(plan, project.architecture)
            affected = set(report.directly_affected + report.transitively_affected)
        except Exception as e:
            print(f"  [!] Impact analysis failed: {e}")

        if not affected:
            affected = set(modulos_by_name.keys())

        source_dir = self._workspace(project) / "source"
        self._notify(
            f"Regenerando {len(affected)} módulo(s) con los cambios solicitados...",
            "PHASE_START", {"phase": "development"},
        )

        for nombre in sorted(affected):
            if nombre not in modulos_by_name:
                continue
            module = {
                **modulos_by_name[nombre],
                "responsabilidad": (
                    modulos_by_name[nombre]["responsabilidad"]
                    + f"\n\nCAMBIO SOLICITADO POR EL USUARIO: {user_request}"
                ),
            }
            self._notify(f"Regenerando: {nombre}", "MODULE_START", {"module": nombre})
            generated_files = await self.code_gen.generate_module(
                module, project.blueprint, project.architecture,
                user_requirements=RequirementsStore(project.workspace).as_task_field(),
            )
            for gf in generated_files:
                out = source_dir / gf.filepath
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(gf.content, encoding="utf-8", errors="replace")
                self._notify(
                    f"Actualizado: {gf.filepath}",
                    "FILE_GENERATED",
                    {"filename": gf.filepath, "code": gf.content, "validated": gf.validated},
                )
            self._notify(f"Módulo actualizado: {nombre}", "MODULE_DONE", {"module": nombre})

        self._save_state(project)

    # ------------------------------------------------------------------ #
    # Phase: Feedback loop                                                 #
    # ------------------------------------------------------------------ #

    async def _run_auto_fix_loop(
        self,
        project: Project,
        boot_report: dict,
        max_retries: int = 3,
    ) -> tuple[bool, dict]:
        """Auto-fix loop: sanitize → fix files → re-boot. Returns (success, updated_boot_report)."""
        import json as _json
        from kernel.agents.auto_fix_agent import AutoFixAgent

        source_dir = self._workspace(project) / "source"
        if not source_dir.exists():
            return False, boot_report

        # Load master_contract for contract enforcement
        master_contract: dict | None = None
        mc_path = self._workspace(project) / "master_contract.json"
        if mc_path.exists():
            try:
                master_contract = _json.loads(mc_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        auto_fixer = AutoFixAgent(
            claude_driver=getattr(self, "claude", None),
            gemini_driver=getattr(self, "gemini", None),
            context_builder=getattr(self, "builder", None),
            notify_fn=self._notify,
        )
        workspace_path = self._workspace(project)

        for attempt in range(max_retries):
            errors = boot_report.get("last_errors", [])
            if not errors:
                break

            self._notify(
                f"Auto-Fix ronda {attempt + 1}/{max_retries}: detectados {len(errors)} error(es)…",
                "HEALTH_WARN",
                {"phase": "auto_fix", "attempt": attempt + 1},
            )

            patched = await auto_fixer.fix_files_from_errors(
                errors=errors,
                raw_stderr="",
                source_dir=source_dir,
                master_contract=master_contract,
                workspace_path=workspace_path,
            )

            if not patched:
                self._notify(
                    "Auto-Fix: no se pudieron identificar archivos para reparar.",
                    "HEALTH_WARN",
                    {"phase": "auto_fix", "attempt": attempt + 1},
                )
                break

            # Re-boot after fixes
            try:
                report = await self.boot_agent.run(source_dir, project.architecture, project.blueprint)
                self._save_phase_report(project, "boot_report.json", report.to_dict())
                boot_report = report.to_dict()
                if report.final_ok:
                    self._notify("Auto-Fix: la aplicación arranca correctamente.", "LOG", {})
                    return True, boot_report
            except Exception as exc:
                self._notify(f"Auto-Fix: re-boot falló: {exc}", "HEALTH_WARN", {"phase": "auto_fix"})
                break

        return False, boot_report

    async def _phase_feedback_loop(self, project: Project, setup_result: dict | None = None) -> None:
        """Ask user for feedback after DONE, apply changes, re-validate, repeat."""
        import json as _json
        MAX_ITERATIONS = 5
        DONE_WORDS = {"listo", "ok", "bien", "perfecto", "ninguno", "no", "no cambios",
                      "nada", "gracias", "todo bien", "funciona", "excelente", "genial"}

        # PASO 4: determine real boot status from boot_report.json and setup_result
        _sr = setup_result or {}
        _smoke_passed = bool(_sr.get("smoke", {}).get("passed"))

        # Load boot_report.json for install/boot status
        _boot_report: dict = {}
        _boot_report_path = self._workspace(project) / "boot_report.json"
        if _boot_report_path.exists():
            try:
                _boot_report = _json.loads(_boot_report_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        _boot_skipped = _boot_report.get("skipped", True)
        _install_passed = _boot_report.get("final_ok", False) or _boot_skipped
        _boot_error_log = ""
        if not _install_passed and _boot_report.get("last_errors"):
            _boot_error_log = "; ".join(
                e.get("message", "") for e in _boot_report["last_errors"][:3]
            )

        _app_running = _smoke_passed and _install_passed

        # PASO 4: si el boot falló y hay errores identificados, correr auto-fix antes de preguntar al usuario
        if not _app_running and not _boot_skipped and _boot_report.get("last_errors"):
            self._notify(
                "Boot falló — activando protocolo de Auto-Fix de Runtime…",
                "PHASE_START",
                {"phase": "auto_fix"},
            )
            _auto_fixed, _boot_report = await self._run_auto_fix_loop(
                project, _boot_report, max_retries=3
            )
            if _auto_fixed:
                _app_running = True
                _boot_error_log = ""
            else:
                # Update error log from the final boot attempt
                _boot_error_log = "; ".join(
                    e.get("message", "") for e in _boot_report.get("last_errors", [])[:3]
                )

        for iteration in range(MAX_ITERATIONS):
            if iteration == 0:
                if _app_running:
                    question = (
                        "La aplicación está corriendo en la pestaña de testeo. "
                        "¿Quedó como esperabas? Describí los cambios que querés (o escribí 'listo' para terminar)."
                    )
                elif not _install_passed and _boot_error_log:
                    # PASO 4: auto-fix ya corrió y agotó sus 3 vidas — pedir intervención humana
                    question = (
                        "El sistema intentó auto-corregir el error 3 veces sin éxito.\n"
                        f"Último error: {_boot_error_log[:400]}\n\n"
                        "La aplicación está en tu disco. Podés revisarla manualmente o indicarme qué cambiar."
                    )
                else:
                    question = (
                        "El código fue generado. Podés ejecutarlo desde el panel de lanzamiento en la UI. "
                        "¿Querés ajustar algo antes de correrlo? Describí los cambios (o escribí 'listo' para terminar)."
                    )
            else:
                question = "¿Cómo quedó con los últimos cambios? Describí qué más querés ajustar (o escribí 'listo')."
            answer = await self.user_interaction.ask(question, self._notify)
            answer_clean = answer.strip().lower()

            if not answer_clean or any(answer_clean == w for w in DONE_WORDS) or answer_clean.startswith("listo"):
                if answer_clean:
                    self._notify("¡Proyecto terminado! Podés seguir usando el botón ▶ para ejecutarlo.", "LOG", {})
                break

            self._notify(f"Aplicando: {answer[:120]}", "LOG", {})
            await self._phase_iteration(project, answer)
            await self._phase_validation(project, skip_permission=True)

            run_command = self._get_run_command(project)
            install_command = self._get_install_command(project)
            self._notify(
                f"Cambios aplicados (iteración {iteration + 1}).",
                "ITERATION_DONE",
                {
                    "project_id": project.id,
                    "run_command": run_command,
                    "install_command": install_command,
                    "workspace": str(project.workspace),
                    "iteration": iteration + 1,
                },
            )

    # ------------------------------------------------------------------ #
    # Phase: Docs                                                          #
    # ------------------------------------------------------------------ #

    async def _phase_docs(self, project: Project) -> None:
        if project.blueprint and project.architecture:
            workspace = self._workspace(project)
            source_dir = workspace / "source"
            if source_dir.exists() and self.service_orchestrator.needs_compose(project.blueprint, project.architecture):
                compose_result = self.service_orchestrator.generate_compose(
                    project.blueprint, project.architecture, source_dir
                )
                if compose_result.generated:
                    self._notify(
                        f"docker-compose.yml generado con servicios: {', '.join(compose_result.services)}",
                        "FILE_GENERATED",
                        {"file": compose_result.path, "services": compose_result.services},
                    )

        self._notify("Generando documentación...", "PHASE_START", {"phase": "docs"})
        try:
            workspace = self._workspace(project)
            source_dir = workspace / "source"
            files = []
            if source_dir.exists():
                files = sorted(
                    str(p.relative_to(source_dir))
                    for p in source_dir.rglob("*") if p.is_file()
                )

            bp_text = json.dumps(project.blueprint, ensure_ascii=False, indent=2)
            arch_text = json.dumps(project.architecture, ensure_ascii=False, indent=2)
            file_list = "\n".join(files[:60]) or "(sin archivos)"

            task = (
                f"BLUEPRINT:\n{bp_text}\n\n"
                f"ARQUITECTURA:\n{arch_text}\n\n"
                f"ARCHIVOS GENERADOS:\n{file_list}"
            )
            content = await self._call_for_role("claude", "docs_generator", task)
            project.reference_report = self._build_reference_report(content)
            self._save_state(project)

            readme_path = (source_dir if source_dir.exists() else workspace) / "README.txt"
            readme_path.write_text(content, encoding="utf-8")
            self._notify(
                f"README.txt generado: {readme_path.name}",
                "FILE_GENERATED",
                {"file": str(readme_path), "reference_report": project.reference_report},
            )
            if project.reference_report.get("broken_candidates", 0) > 0:
                self._notify(
                    "La documentación generada contiene referencias potencialmente rotas.",
                    "HEALTH_WARN",
                    {"phase": "docs", "reference_report": project.reference_report},
                )

            outputs_dir = workspace / "_soda_outputs"
            try:
                output_results = self.output_generator.generate_all(
                    project_id=project.id,
                    blueprint=project.blueprint or {},
                    architecture=project.architecture or {},
                    reference_report=project.reference_report or {},
                    output_dir=outputs_dir,
                )
                for out in output_results:
                    if out.success:
                        self._notify(
                            f"Output generado: {out.format} → {out.path}",
                            "FILE_GENERATED",
                            {"file": out.path, "format": out.format, "size": out.size_bytes},
                        )
            except Exception as out_err:
                self._notify(f"Output generation omitida: {out_err}", "LOG", {})

        except Exception as e:
            self._notify(f"Documentación omitida: {e}", "LOG")

    # ------------------------------------------------------------------ #
    # Phase: Evolution                                                     #
    # ------------------------------------------------------------------ #

    async def _phase_evolution(self, project: Project) -> None:
        if not project.profile:
            return
        print("\n[POST] Profile Evolution — capturing learnings...")
        self._notify("Capturando aprendizajes...", "PHASE_START", {"phase": "evolution"})
        try:
            learnings = await self.profile_evolution.evolve(
                project.id, project.description,
                project.blueprint, project.architecture,
                project.profile, project.skills,
            )
            count = (
                len(learnings.get("patterns", []))
                + len(learnings.get("anti_patterns", []))
                + len(learnings.get("preferences", []))
            )
            print(f"  [OK] {count} learning(s) written to profile '{project.profile}'")
            self._notify(
                f"{count} aprendizajes guardados en perfil '{project.profile}'",
                "EVOLUTION",
                {"profile": project.profile, "count": count, "learnings": learnings},
            )
            evo_sug = await self.copilot_consultant.review_evolution(learnings, project.description)
            self._handle_copilot_review(evo_sug, "evolution")
        except Exception as e:
            print(f"  [!] Evolution failed (non-critical): {e}")

        try:
            new_patterns = self.knowledge_base.synthesize_from_observations()
            if new_patterns > 0:
                print(f"  [KB] {new_patterns} nuevo(s) patrón(es) sintetizados en base de conocimiento")
                self._notify(
                    f"Knowledge Base: {new_patterns} patrón(es) nuevos aprendidos",
                    "EVOLUTION",
                    {"type": "knowledge_synthesis", "new_patterns": new_patterns},
                )
        except Exception as e:
            print(f"  [!] Knowledge synthesis failed (non-critical): {e}")

    # ------------------------------------------------------------------ #
    # Helper: phase report persistence                                     #
    # ------------------------------------------------------------------ #

    def _save_phase_report(self, project: Project, filename: str, data: dict) -> None:
        try:
            out = self._workspace(project) / filename
            out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Phase: Requirements (FASE 1)                                         #
    # ------------------------------------------------------------------ #

    async def _phase_requirements(self, project: Project) -> None:
        from kernel.orchestrator import ProjectState
        print("\n[FASE 1] Requirements — interviewing with Claude Sonnet...")
        self._notify("Analizando requerimientos...", "PHASE_START", {"phase": "requirements"})
        project.state = ProjectState.REQUIREMENTS

        history_hint = self.knowledge_orchestrator.enrich_context_with_history(project.description)
        task_input = project.description
        if history_hint:
            task_input = (
                f"{project.description}\n\n"
                f"<historial_proyectos>\n{history_hint}\n</historial_proyectos>"
            )
            self._notify("Memoria vectorial: proyectos similares encontrados.", "LOG", {})

        MAX_COPILOT_REGEN = self._copilot_phase_regen
        for regen in range(MAX_COPILOT_REGEN + 1):
            max_attempts = 3
            for attempt in range(max_attempts):
                response = await self._call_for_role("claude", "requirements_interviewer", task_input, project)
                project.blueprint = self._extract_json(response)
                if "raw" not in project.blueprint and "nombre_proyecto" in project.blueprint:
                    break
                self._notify(
                    f"Advertencia: blueprint malformado (intento {attempt+1}/{max_attempts}). Reintentando...",
                    "HEALTH_WARN", {"phase": "requirements", "raw_preview": str(response)[:200]},
                )

            if "raw" in project.blueprint and "nombre_proyecto" not in project.blueprint:
                raise ValueError("No se pudo generar un blueprint JSON válido tras 3 intentos.")

            suggestion = await self.copilot_consultant.review_blueprint(project.blueprint, project.description)
            handled = self._handle_copilot_review(suggestion, "requirements")
            if regen < MAX_COPILOT_REGEN and handled["applied"] and handled["strategy"] in ("regenerate", "rephase"):
                numbered = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(handled["changes"]))
                project.description += f"\n\nSUGERENCIA COPILOT APLICADA:\n{numbered}"
                self._apply_project_type(project)
                self._apply_capability_packs(project)
                task_input = project.description
                self._notify("Regenerando blueprint con la sugerencia de Copilot...", "LOG", {})
                continue
            break

        bp_val = BlueprintValidator().validate(project.blueprint)
        if bp_val.auto_fixes:
            project.blueprint = bp_val.fixed_architecture
            self._notify(
                f"Blueprint auto-corregido: {len(bp_val.auto_fixes)} ajuste(s).",
                "LOG", {"fixes": bp_val.auto_fixes},
            )
        for w in bp_val.warnings:
            self._notify(w, "HEALTH_WARN", {"phase": "requirements_validation"})
        if not bp_val.is_valid:
            raise ValueError(f"Blueprint inválido: {'; '.join(bp_val.errors)}")

        # Stack confirmation: if Claude inferred technologies not mentioned by the user,
        # ask for confirmation and allow one correction pass.
        project.blueprint = await self._confirm_stack_with_user(project)

        nombre = project.blueprint.get("nombre_proyecto", project.id)
        out = self._workspace(project) / "blueprint.json"
        out.write_text(json.dumps(project.blueprint, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [OK] Blueprint -> {out}")
        self._notify("Blueprint listo.", "CHECKPOINT", {"number": 1, "project_name": nombre})
        self._save_state(project)

    # ------------------------------------------------------------------ #
    # Legacy migration helper                                              #
    # ------------------------------------------------------------------ #

    async def _migrate_legacy_architecture(self, project: Project) -> None:
        """Lazy migration: convert architecture.json (v1) to topology.json + master_contract.json (v2).

        Called during resume when a project has architecture.json but not topology.json.
        Steps:
          1. Translate architecture.json modules → topology.json (snake_case IDs)
          2. Run Claude (Fase 2B) to generate master_contract.json from the topology
          3. Rename architecture.json → architecture.json.legacy.bak
        """
        import re as _re
        workspace = self._workspace(project)
        arch_path = workspace / "architecture.json"

        # Load legacy architecture if not in memory
        if not project.architecture:
            try:
                project.architecture = json.loads(arch_path.read_text(encoding="utf-8"))
            except Exception as exc:
                self._notify(f"Migración legacy: no se pudo leer architecture.json: {exc}", "HEALTH_WARN", {})
                return

        old_arch = project.architecture
        old_modulos = old_arch.get("modulos", [])
        if not old_modulos:
            return

        # Build id_map: "Módulo Auth" → "modulo_auth"
        def to_snake(name: str) -> str:
            slug = _re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            return _re.sub(r"_+", "_", slug) or "module"

        id_map: dict[str, str] = {}
        seen: set[str] = set()
        for i, mod in enumerate(old_modulos):
            raw = str(mod.get("nombre", f"module_{i}"))
            cand = to_snake(raw)
            if cand in seen:
                cand = f"{cand}_{i}"
            id_map[raw] = cand
            seen.add(cand)

        # Build topology.json
        topo_modulos = []
        for mod in old_modulos:
            mod_id = id_map.get(mod.get("nombre", ""), to_snake(mod.get("nombre", "module")))
            topo_modulos.append({
                "id": mod_id,
                "responsabilidad": mod.get("responsabilidad", ""),
                "archivos_principales": mod.get("archivos_principales", []),
                "depende_de_ids": [
                    id_map.get(dep, to_snake(dep))
                    for dep in mod.get("dependencias", [])
                    if dep != mod.get("nombre", "")
                ],
            })

        topology = {
            "stack": old_arch.get("stack", old_arch.get("stack_sugerido", {})),
            "modulos": topo_modulos,
            "decisiones_clave": old_arch.get("decisiones_clave", []),
            "advertencias": old_arch.get("advertencias", []),
        }
        project.topology = topology
        topo_out = workspace / "topology.json"
        topo_out.write_text(json.dumps(topology, indent=2, ensure_ascii=False), encoding="utf-8")
        self._notify(f"Migración: topology.json generado ({len(topo_modulos)} módulos).", "LOG", {})

        # Ensure blueprint is loaded
        if not project.blueprint:
            bp_path = workspace / "blueprint.json"
            if bp_path.exists():
                try:
                    project.blueprint = json.loads(bp_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

        # Run Claude (Fase 2B only) to type the contract
        await self._phase_master_contract(project)

        # Rename legacy file so it doesn't re-trigger migration
        bak_path = arch_path.with_suffix(".json.legacy.bak")
        try:
            arch_path.rename(bak_path)
        except Exception:
            pass  # Non-fatal — topology.json being present is the guard

        self._notify("Migración legacy completada. topology.json + master_contract.json listos.", "LOG", {})

    # ------------------------------------------------------------------ #
    # Stack confirmation helper (FASE 1 post-step)                         #
    # ------------------------------------------------------------------ #

    async def _confirm_stack_with_user(self, project: Project) -> dict:
        """Ask the user to confirm inferred stack technologies.

        If Claude picked technologies not explicitly mentioned in the user's
        description, surface them for confirmation. On disagreement, concatenate
        the user's preference to project.description and regenerate the blueprint
        once (one extra attempt, no recursion).
        """
        blueprint = project.blueprint
        stack = blueprint.get("stack_sugerido", {})
        desc_lower = project.description.lower()

        inferred = [
            tech for tech in stack.values()
            if isinstance(tech, str) and tech and tech.lower() not in desc_lower
        ]

        if not inferred:
            return blueprint

        stack_display = ", ".join(f"{k}: {v}" for k, v in stack.items() if isinstance(v, str) and v)
        pregunta = (
            f"Inferí el siguiente stack para tu proyecto: {stack_display}. "
            f"¿Estás de acuerdo o preferís cambiar algo? (Respondé con detalles o escribí 'ok' para confirmar)"
        )
        self._notify(pregunta, "ASK_USER", {"stack": stack})
        respuesta = await self.user_interaction.ask(pregunta, self._notify)

        if not respuesta or respuesta.strip().lower() in ("ok", "si", "sí", "yes", "bien", "perfecto", "dale"):
            return blueprint

        # User wants changes — re-run Claude once with the preference appended
        self._notify("Regenerando blueprint con preferencia de stack del usuario...", "LOG", {})
        project.description += f"\n\nPreferencia de stack del usuario: {respuesta.strip()}"
        task_input = project.description
        history_hint = self.knowledge_orchestrator.enrich_context_with_history(project.description)
        if history_hint:
            task_input = (
                f"{project.description}\n\n"
                f"<historial_proyectos>\n{history_hint}\n</historial_proyectos>"
            )

        response = await self._call_for_role("claude", "requirements_interviewer", task_input, project)
        new_blueprint = self._extract_json(response)
        if "nombre_proyecto" in new_blueprint and "raw" not in new_blueprint:
            bp_val = BlueprintValidator().validate(new_blueprint)
            fixed = bp_val.fixed_architecture if bp_val.auto_fixes else new_blueprint
            self._notify("Blueprint regenerado con stack corregido.", "LOG", {})
            return fixed

        # If regen failed, keep original and warn
        self._notify(
            "No se pudo regenerar el blueprint con el stack preferido — se mantiene el original.",
            "HEALTH_WARN", {"phase": "requirements_stack_confirm"},
        )
        return blueprint

    # ------------------------------------------------------------------ #
    # Phase: Architecture (FASE 2) — Topology + Master Contract            #
    # ------------------------------------------------------------------ #

    async def _phase_architecture(self, project: Project) -> None:
        """Two-step architecture phase.

        Step 2A: Gemini generates topology.json — physical module structure
                 (IDs, files, DAG edges). No contracts, no interfaces.
        Step 2B: Claude reads topology + blueprint and generates master_contract.json
                 with typed interfaces, data_types and error_types.
        Planning (Fase 3) and Development (Fase 4) read master_contract.json.
        topology.json is the single source of truth for module IDs and dependencies.
        """
        from kernel.orchestrator import ProjectState
        print("\n[FASE 2] Architecture — topology (Gemini) + contract (Claude)...")
        self._notify("Diseñando arquitectura...", "PHASE_START", {"phase": "architecture"})
        project.state = ProjectState.ARCHITECTURE

        # ── 2A: Gemini → topology.json ────────────────────────────────────────
        topology = await self._phase_topology(project)
        project.topology = topology

        # Save topology.json as the new primary artifact
        topo_out = self._workspace(project) / "topology.json"
        topo_out.write_text(json.dumps(topology, indent=2, ensure_ascii=False), encoding="utf-8")

        # Derive architecture.json from topology for backward compatibility
        # (any code that still reads architecture.json will get a compatible view)
        project.architecture = self._topology_to_legacy_architecture(topology)
        arch_out = self._workspace(project) / "architecture.json"
        arch_out.write_text(json.dumps(project.architecture, indent=2, ensure_ascii=False), encoding="utf-8")

        self._build_goal_tree(project)
        print(f"  [OK] Topology  → {topo_out}")
        print(f"  [OK] Arch compat → {arch_out}")
        self._notify("Topología lista.", "LOG", {"modules": [m.get("id") for m in topology.get("modulos", [])]})

        try:
            modulos = topology.get("modulos", [])
            self.observer.record_architecture(
                provider="gemini",
                project_type=str(project.blueprint.get("tipo_proyecto", "")),
                description_summary=project.description[:300],
                module_count=len(modulos),
                stack=project.blueprint.get("stack_sugerido", {}),
                architecture_snippet=json.dumps({"modulos": [m.get("id") for m in modulos]})[:800],
                project_id=project.id,
            )
        except Exception:
            pass

        # ── 2B: Claude → master_contract.json ────────────────────────────────
        await self._phase_master_contract(project)

        self._notify("Arquitectura lista.", "CHECKPOINT", {"number": 2})
        self._save_state(project)

    async def _phase_topology(self, project: Project) -> dict:
        """Call Gemini to produce topology.json (Fase 2A)."""
        complexity = getattr(project, "complexity_level", "medium") or "medium"
        complexity_hints = {
            "simple": "Agrupa en la menor cantidad de módulos posible (monolito). Minimizá la cantidad de archivos.",
            "medium": "Separación estándar por capas: presentación, lógica de negocio, persistencia.",
            "complex": "Aplicá separación estricta de capas (Clean Architecture). Cada responsabilidad en su propio módulo.",
        }
        complexity_hint = complexity_hints.get(str(complexity), complexity_hints["medium"])

        blueprint_str = json.dumps(project.blueprint, ensure_ascii=False)
        req_block = RequirementsStore(project.workspace).as_constraint_block()
        if req_block:
            blueprint_str = req_block + "\n" + blueprint_str

        topo_input = f"[COMPLEJIDAD] {complexity_hint}\n\n{blueprint_str}"

        max_attempts = 3
        last_response = ""
        _primary = self._resolve_primary_provider("gemini", "global_architect")
        topology: dict = {}

        for attempt in range(max_attempts):
            if _primary == "gemini":
                last_response = await self._call_gemini(
                    "global_architect", topo_input, project,
                    response_format="json", max_tokens=16384,
                )
            else:
                last_response = await self._call_for_role(
                    "gemini", "global_architect", topo_input, project
                )
            topology = self._extract_json(last_response)
            if "raw" not in topology and "modulos" in topology:
                break
            self._notify(
                f"Topología malformada (intento {attempt+1}/{max_attempts}). Reintentando...",
                "HEALTH_WARN",
                {"phase": "topology", "attempt": attempt + 1},
            )

        if "modulos" not in topology:
            self._notify(
                "Gemini falló 3 veces — escalando a Claude para topología...",
                "HEALTH_WARN", {"phase": "topology"},
            )
            claude_resp = await self._call_claude("global_architect", topo_input, project)
            topology = self._extract_json(claude_resp)
            if "modulos" not in topology:
                raise ValueError("No se pudo generar una topología JSON válida (Gemini×3 + Claude fallback).")

        # Validate and auto-fix topology (paths, duplicate IDs, circular deps)
        topology = self._validate_topology(topology, project.blueprint)
        return topology

    def _validate_topology(self, topology: dict, blueprint: dict) -> dict:
        """Validate topology.json structure and auto-fix common issues."""
        import copy
        import re as _re
        topo = copy.deepcopy(topology)
        modulos = topo.get("modulos", [])

        seen_ids: set[str] = set()
        clean: list[dict] = []

        for i, mod in enumerate(modulos):
            if not isinstance(mod, dict):
                continue
            raw_id = str(mod.get("id") or mod.get("nombre", "")).strip()
            if not raw_id:
                raw_id = f"module_{i}"
            mod["id"] = raw_id
            # Normalize to snake_case
            normalized = _re.sub(r"[^a-z0-9_]", "_", raw_id.lower()).strip("_")
            normalized = _re.sub(r"_+", "_", normalized) or f"module_{i}"
            if normalized != raw_id:
                self._notify(f"Topología: ID normalizado '{raw_id}' → '{normalized}'", "LOG", {})
                mod["id"] = normalized
            if normalized in seen_ids:
                normalized = f"{normalized}_{i}"
                mod["id"] = normalized
            seen_ids.add(normalized)

            # Normalize file paths using ArchitectureValidator's helper
            from kernel.validation.architecture_validator import ArchitectureValidator as _AV
            good_paths = []
            for raw_path in mod.get("archivos_principales", []):
                fixed, err = _AV._normalize_path(str(raw_path).strip())
                if not err:
                    good_paths.append(fixed)
            mod["archivos_principales"] = good_paths

            if not isinstance(mod.get("depende_de_ids"), list):
                mod["depende_de_ids"] = []

            clean.append(mod)

        topo["modulos"] = clean

        # Remove invalid cross-references in depende_de_ids
        for mod in topo["modulos"]:
            mod["depende_de_ids"] = [
                d for d in mod["depende_de_ids"]
                if d != mod["id"] and d in seen_ids
            ]

        # Apply arch_fixer for frontend→backend dependency
        # Build a temporary legacy-format arch for the fixer
        tmp_arch = self._topology_to_legacy_architecture(topo)
        from kernel.intelligence.arch_fixer import fix_frontend_backend_deps
        tmp_arch = fix_frontend_backend_deps(tmp_arch)
        # Reflect any added deps back into topology
        id_map = {m["nombre"]: m for m in tmp_arch.get("modulos", [])}
        for mod in topo["modulos"]:
            legacy = id_map.get(mod["id"])
            if legacy:
                fixed_deps = [
                    _id for dep_name in legacy.get("dependencias", [])
                    for _id in [dep_name]
                    if _id in seen_ids
                ]
                mod["depende_de_ids"] = fixed_deps

        # Also run build-infrastructure injection
        arch_val = ArchitectureValidator().validate(tmp_arch, blueprint)
        if arch_val.auto_fixes:
            # Re-sync any new infraestructura_build module back to topology
            existing_ids = {m["id"] for m in topo["modulos"]}
            for fixed_mod in arch_val.fixed_architecture.get("modulos", []):
                mod_id = _re.sub(r"[^a-z0-9_]", "_", fixed_mod.get("nombre", "").lower()).strip("_")
                if mod_id and mod_id not in existing_ids:
                    topo["modulos"].insert(0, {
                        "id": mod_id,
                        "responsabilidad": fixed_mod.get("responsabilidad", ""),
                        "archivos_principales": fixed_mod.get("archivos_principales", []),
                        "depende_de_ids": [],
                    })
                    self._notify(f"Topología: módulo '{mod_id}' inyectado (build infra).", "LOG", {})

        return topo

    @staticmethod
    def _topology_to_legacy_architecture(topology: dict) -> dict:
        """Convert topology.json to architecture.json format for backward compatibility."""
        return {
            "stack": topology.get("stack", {}),
            "modulos": [
                {
                    "nombre": m["id"],
                    "responsabilidad": m.get("responsabilidad", ""),
                    "archivos_principales": m.get("archivos_principales", []),
                    "dependencias": m.get("depende_de_ids", []),
                    "endpoints": [],
                }
                for m in topology.get("modulos", [])
                if isinstance(m, dict) and m.get("id")
            ],
            "contratos": [],
            "decisiones_clave": topology.get("decisiones_clave", []),
            "advertencias": topology.get("advertencias", []),
        }

    @staticmethod
    def _build_goal_tree_from_blueprint(blueprint: dict) -> dict:
        """Derive a minimal goal_tree from blueprint funcionalidades.

        Gives the Architect real goal IDs to reference instead of inventing them,
        enabling full TraceabilityValidator mode instead of soft mode.
        """
        funcs = blueprint.get("funcionalidades", [])
        if not funcs:
            return {}
        children = []
        seen: set[str] = set()
        for i, f in enumerate(funcs):
            name = f.get("nombre", f"objetivo_{i+1}") if isinstance(f, dict) else str(f)
            raw = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
            goal_id = raw[:40] or f"goal_{i+1}"
            if goal_id in seen:
                goal_id = f"{goal_id}_{i}"
            seen.add(goal_id)
            children.append({"id": goal_id, "name": name, "children": []})
        return {
            "id": "root",
            "name": blueprint.get("nombre_proyecto", "root"),
            "children": children,
        }

    # ------------------------------------------------------------------ #
    # Phase: Development (FASE 4)                                          #
    # ------------------------------------------------------------------ #

    async def _phase_development(self, project: Project, plan: ExecutionPlan, interactive_mode: bool = False, skip_existing: bool = False) -> None:
        from kernel.orchestrator import ProjectState
        print("\n[FASE 4] Development — generating code...")
        self._notify("Generando código...", "PHASE_START", {"phase": "development"})

        project.state = ProjectState.DEVELOPMENT
        intensity_profile = self.intensity.choose_profile(project.description)
        modulos_by_name = {m["nombre"]: m for m in project.architecture.get("modulos", [])}
        source_dir = self._workspace(project) / "source"
        source_dir.mkdir(exist_ok=True)

        # Load master_contract.json once for the whole development phase.
        # Its typed interfaces will be injected into each module's task context.
        _mc_path = self._workspace(project) / "master_contract.json"
        _master_contract: dict | None = None
        if _mc_path.exists():
            try:
                _master_contract = json.loads(_mc_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Template injection: find → validate → inject (or skip and save later)
        from kernel.execution.template_injector import TemplateInjector
        _templates_dir = source_dir.parent.parent.parent / "templates"
        _injector = TemplateInjector(_templates_dir)
        _template_dir = _injector.find_best_template(project.blueprint)
        _template_used = False
        if _template_dir:
            _valid, _reason = _injector.validate(_template_dir)
            if _valid:
                _injected = set(_injector.inject(_template_dir, source_dir))
                self.code_gen.injected_files = _injected
                _template_used = True
                self._notify(
                    f"Plantilla '{_template_dir.name}' aplicada ({len(_injected)} archivo(s) inyectados)",
                    "LOG",
                    {"template": str(_template_dir), "injected": len(_injected)},
                )
            else:
                self._notify(
                    f"Plantilla encontrada pero inválida ({_reason}) — generando desde cero",
                    "LOG",
                    {"template": str(_template_dir), "reason": _reason},
                )
        else:
            self._notify("Sin plantilla para este stack — generando desde cero", "LOG", {})

        # D — pre-warm Qwen + setup sandbox env in parallel while first level generates
        _warmup = self.code_gen.ollama.warmup()
        if asyncio.iscoroutine(_warmup):
            asyncio.create_task(_warmup)

        from kernel.sandbox.dynamic_env import DynamicEnvironment
        _sandbox_env = DynamicEnvironment(project.id, self._workspace(project), self._notify)

        async def _setup_sandbox_env():
            if await _sandbox_env.ensure_venv():
                await _sandbox_env.install_requirements()

        _sandbox_setup_task = asyncio.create_task(_setup_sandbox_env())

        from kernel.execution.html_template_injector import inject_for_project as _inject_html
        _inject_html(source_dir, project.blueprint, project.architecture)
        design_injector = DesignContextInjector(self._workspace(project))

        skills_context: Optional[str] = None
        profile_context: Optional[str] = None
        try:
            if project.skills:
                skills_context = self.skill_manager.load_context(project.skills, role="code_generator") or None
            if project.profile:
                profile_context = self.profile_manager.load_context(project.profile) or None
        except Exception as _e:
            self._notify(f"Skills/profile context no disponible: {_e}", "LOG", {})

        module_generated_code: dict[str, dict[str, str]] = {}
        _runtime_errors: str = ""  # errors from previous level passed to next level's generation

        nombres_en_nivel = [
            [n for n in level if n in modulos_by_name]
            for level in plan.levels
        ]
        total_levels = len(nombres_en_nivel)
        for i, level in enumerate(plan.levels):
            nombres = nombres_en_nivel[i]
            tag = f"[parallel x{len(nombres)}]" if len(nombres) > 1 else "[sequential]"
            print(f"\n  Level {i} {tag}: {' | '.join(nombres)}")

            if interactive_mode:
                answer = await self.user_interaction.ask(
                    f"Listo para generar Nivel {i} ({', '.join(nombres)}). ¿Continuar? (sí/no/saltar)",
                    self._notify
                )
                if answer.strip().lower() in ("no", "n"):
                    raise RuntimeError("Ejecución pausada por el usuario en modo interactivo.")
                elif answer.strip().lower() in ("saltar", "skip"):
                    self._notify(f"Saltando Nivel {i} a petición del usuario.", "LOG", {})
                    continue

            if skip_existing:
                nombres_to_gen = []
                for nombre in nombres:
                    mod = modulos_by_name[nombre]
                    expected = mod.get("archivos_principales", [])
                    missing = [f for f in expected if not (source_dir / f).exists()]
                    if not missing:
                        print(f"  [RESUME] Saltando módulo completo: {nombre}")
                        self._notify(f"Módulo ya generado: {nombre}", "LOG", {"module": nombre})
                    else:
                        print(f"  [RESUME] Módulo incompleto ({len(missing)} archivo/s faltantes): {nombre}")
                        nombres_to_gen.append(nombre)
                nombres = nombres_to_gen
                if not nombres:
                    continue

            for nombre in nombres:
                self._notify(f"Generando módulo: {nombre}", "MODULE_START", {"module": nombre, "level": i})
            tasks = [
                self._dev_qwen_copilot_loop(
                    modulos_by_name[nombre], project, source_dir,
                    dependency_context=module_generated_code,
                    skills_context=skills_context,
                    profile_context=profile_context,
                    design_injector=design_injector,
                    runtime_errors=_runtime_errors,
                    master_contract=_master_contract,
                )
                for nombre in nombres
            ]
            results_per_module = await asyncio.gather(*tasks, return_exceptions=True)
            for nombre, result in zip(nombres, results_per_module):
                if isinstance(result, Exception):
                    self._notify(
                        f"Módulo {nombre} falló (omitido): {result}",
                        "HEALTH_WARN",
                        {"module": nombre, "error": str(result)},
                    )
                    print(f"  [DEV] Módulo {nombre} error: {result}")
                    continue
                generated_files = result
                module_generated_code[nombre] = {gf.filepath: gf.content for gf in generated_files}
                if intensity_profile.review_required or intensity_profile.arbiter_required:
                    await self._intensity_copilot_loop(
                        nombre, modulos_by_name[nombre], generated_files,
                        source_dir, project, intensity_profile,
                    )
                self._notify(f"Módulo listo: {nombre}", "MODULE_DONE", {"module": nombre, "level": i})

            # Wait for sandbox env to be ready (may already be done by now)
            if not _sandbox_setup_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(_sandbox_setup_task), timeout=5.0)
                except asyncio.TimeoutError:
                    pass  # still installing — skip execution check this level

            # Per-level runtime check: syntax + startup probe (fix up to 2 times if it crashes)
            _runtime_errors = await self._level_runtime_check(
                _sandbox_env, source_dir, nombres, modulos_by_name,
                project, module_generated_code, skills_context, profile_context,
                is_last_level=(i == total_levels - 1),
            )

        print(f"\n  [OK] Code generated -> {source_dir}")

        # Save as template for future projects if we didn't use one
        if not _template_used:
            try:
                _saved = _injector.save_as_template(source_dir, project.blueprint)
                if _saved:
                    self._notify(
                        f"Nueva plantilla guardada: {_saved.name} (para proyectos similares)",
                        "LOG",
                        {"template": str(_saved)},
                    )
            except Exception as _te:
                self._notify(f"save_as_template falló (no crítico): {_te}", "LOG", {})

        self._save_goal_tree(project)
        self._save_state(project)

        # ── Sandbox: test entorno dinamico (no bloqueante) ────────────────
        asyncio.create_task(self._phase_sandbox(project, source_dir))

    async def _level_runtime_check(
        self,
        env,
        source_dir,
        module_names: list,
        modulos_by_name: dict,
        project,
        module_generated_code: dict,
        skills_context,
        profile_context,
        is_last_level: bool = False,
        max_fix_rounds: int = 2,
    ) -> str:
        """Run syntax check + startup probe after a DAG level. Fix crashing modules up to
        max_fix_rounds times. Returns an error summary string for the next level's context."""
        from kernel.sandbox.dynamic_env import DynamicEnvironment
        from kernel.intelligence.arch_fixer import _is_frontend

        # 1. Syntax check (fast — py_compile only)
        syntax = await env.run_syntax_check(source_dir)
        if syntax.errors:
            err_lines = [
                f"{e.get('file','?')}:{e.get('line','?')} — {e.get('message','')[:100]}"
                for e in syntax.errors[:5]
            ]
            self._notify(
                f"[Runtime check] {len(syntax.errors)} error(es) de sintaxis en nivel {', '.join(module_names)}",
                "HEALTH_WARN",
                {"phase": "dev_runtime_check", "modules": module_names, "errors": syntax.errors[:5]},
            )
            return "ERRORES DE SINTAXIS:\n" + "\n".join(err_lines)

        # 2. Startup probe — only for backend/full levels, not pure frontend
        is_all_frontend = all(
            _is_frontend(modulos_by_name.get(n, {})) for n in module_names
        )
        if is_all_frontend:
            return ""

        # Check if there's a runnable entry point already on disk
        entry_point_exists = any(
            (source_dir / ep).exists()
            for ep in ("main.py", "app.py", "run.py", "server.py", "manage.py")
        )
        if not entry_point_exists:
            return ""

        entry_cmd = (project.blueprint or {}).get("comando_ejecucion") or None

        for fix_round in range(max_fix_rounds + 1):
            startup = await env.run_startup_check(entry_cmd, startup_timeout=12)
            if startup.success:
                if fix_round == 0:
                    self._notify(
                        f"[Runtime check] Nivel {', '.join(module_names)}: arranque OK",
                        "LOG",
                        {"phase": "dev_runtime_check", "modules": module_names},
                    )
                else:
                    self._notify(
                        f"[Runtime check] Corregido tras {fix_round} ronda(s) — arranque OK",
                        "LOG",
                        {"phase": "dev_runtime_check", "modules": module_names, "fix_rounds": fix_round},
                    )
                return ""

            # Startup failed — build error summary
            error_lines = [
                f"{e.get('file','?')}:{e.get('line','?')} — {e.get('message','')[:120]}"
                for e in startup.errors[:6]
            ]
            if not error_lines and startup.stderr:
                error_lines = [startup.stderr[-600:]]

            error_summary = "ERRORES DE RUNTIME (nivel anterior):\n" + "\n".join(error_lines)
            self._notify(
                f"[Runtime check] {len(startup.errors)} error(es) de runtime en nivel {', '.join(module_names)}"
                + (f" — fix ronda {fix_round + 1}/{max_fix_rounds}" if fix_round < max_fix_rounds else " — sin más reintentos"),
                "HEALTH_WARN",
                {"phase": "dev_runtime_check", "modules": module_names,
                 "errors": startup.errors[:6], "fix_round": fix_round},
            )

            if fix_round >= max_fix_rounds:
                return error_summary

            # Identify which modules own the failing files and regenerate them
            failing_files = {e.get("file", "") for e in startup.errors}
            failing_modules = []
            for nombre in module_names:
                mod_files = modulos_by_name.get(nombre, {}).get("archivos_principales", [])
                if any(
                    fp in ff or ff.endswith(fp)
                    for fp in mod_files for ff in failing_files
                ):
                    failing_modules.append(nombre)
            if not failing_modules:
                failing_modules = list(module_names)

            self._notify(
                f"[Runtime check] Regenerando {len(failing_modules)} módulo(s): {', '.join(failing_modules)}",
                "LOG",
                {"phase": "dev_runtime_check", "regenerating": failing_modules},
            )
            await self._phase_targeted_regeneration(
                project, failing_modules,
                errors_final="\n".join(error_lines),
            )
            # Update generated code cache
            for nombre in failing_modules:
                mod_files = modulos_by_name.get(nombre, {}).get("archivos_principales", [])
                files: dict = {}
                for fp in mod_files:
                    fpath = source_dir / fp
                    if fpath.exists():
                        try:
                            files[fp] = fpath.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            pass
                if files:
                    module_generated_code[nombre] = files

        return ""

    async def _phase_sandbox(self, project, source_dir: "Path") -> None:
        """Create isolated venv, install deps, run syntax + execution tests."""
        from kernel.sandbox.dynamic_env import DynamicEnvironment
        try:
            workspace = self._workspace(project)
            entry_cmd = (project.blueprint or {}).get("comando_ejecucion") or None
            env = DynamicEnvironment(
                project_id=project.id,
                workspace=workspace,
                notify_fn=self._notify,
            )
            results = await env.full_cycle(entry_command=entry_cmd)

            if results.get("syntax_errors") or results.get("run_errors"):
                all_errors = results.get("syntax_errors", []) + results.get("run_errors", [])
                error_summary = "; ".join(
                    f"{e.get('file','?')}:{e.get('line','?')} — {e.get('message','')[:80]}"
                    for e in all_errors[:5]
                )
                self._notify(
                    f"Sandbox detectó {len(all_errors)} error(es): {error_summary}",
                    "SANDBOX_REPORT",
                    {"project_id": project.id, "errors": all_errors},
                )
        except Exception as exc:
            self._notify(
                f"Sandbox (no critico): {type(exc).__name__}: {exc}",
                "HEALTH_WARN",
                {"phase": "sandbox", "error": str(exc)},
            )

    # ------------------------------------------------------------------ #
    # Phase: Validation (FASE 4.5)                                         #
    # ------------------------------------------------------------------ #

    async def _phase_validation(self, project: Project, skip_permission: bool = False) -> dict:
        from kernel.project_validator import ProjectValidator
        from kernel.utils.env_checker import check_stack_tools
        print("\n[FASE 4.5] Validation — env check + build + auto-fix...")
        self._notify("Verificando entorno y corrigiendo código...", "PHASE_START", {"phase": "validation"})

        workspace = self._workspace(project)
        source_dir = workspace / "source"
        if not source_dir.exists():
            self._notify("Sin directorio source — omitiendo validación.", "LOG", {})
            return {"skipped": True, "fixed": False, "rounds": 0}

        install_cmd = self._get_install_command(project)
        run_cmd = self._get_run_command(project)

        tools = await check_stack_tools(run_cmd, install_cmd)
        missing = [t for t in tools if not t.available]
        for t in tools:
            icon = "✓" if t.available else "✗"
            self._notify(
                f"{icon} {t.required_for}{': ' + t.version if t.available else ' — no encontrado'}",
                "ENV_CHECK",
                {"tool": t.name, "available": t.available, "version": t.version, "required_for": t.required_for},
            )
        if missing:
            names = ", ".join(t.required_for for t in missing)
            self._notify(
                f"Herramientas faltantes: {names}. Instalálas manualmente para ejecutar el proyecto.",
                "HEALTH_WARN",
                {"missing_tools": [t.name for t in missing]},
            )

        needs_install = bool(install_cmd) or any(
            x in (run_cmd or "").lower()
            for x in ("pip", "npm", "dotnet", "go ", "cargo")
        )
        auto_confirm = self._get_auto_confirm()

        if needs_install:
            self._notify("Instalando dependencias del proyecto...", "LOG", {})

        validator = ProjectValidator(
            claude_driver=self.claude,
            gemini_driver=self.gemini,
            context_builder=self.builder,
            notify_fn=self._notify,
        )

        result = await validator.validate_and_fix(
            source_dir=source_dir,
            install_cmd=install_cmd,
            run_cmd=run_cmd,
            project_description=project.description,
            workspace=workspace,
            architecture=project.architecture,
        )

        if result.get("skipped"):
            self._notify("Validación omitida (stack sin comando de build).", "LOG", {})
        elif result.get("fixed"):
            self._notify(
                f"Código validado y funcional tras {result['rounds']} ronda(s).",
                "CHECKPOINT",
                {"phase": "validation", "rounds": result["rounds"], "success": True},
            )
        else:
            self._notify(
                f"Advertencia: errores de build pendientes tras {result['rounds']} ronda(s).",
                "HEALTH_WARN",
                {
                    "phase": "validation",
                    "rounds": result["rounds"],
                    "failed_modules": result.get("failed_modules", []),
                },
            )

        return result
