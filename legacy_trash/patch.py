import re

with open("kernel/orchestration/phase_mixin.py", "r", encoding="utf-8") as f:
    content = f.read()

start_marker = '    async def _phase_master_contract(self, project: Project) -> None:'
end_marker = '        # Rename legacy file so it doesn\'t re-trigger migration'

new_func = """    async def _phase_master_contract(self, project: Project) -> None:
        try:
            from kernel.intelligence.complexity_classifier import ProjectComplexityClassifier
            from kernel.intelligence.architect import Architect
            from kernel.integrity.contract_auditor import ContractAuditor
            from kernel.orchestration.contract_refinement_loop import ContractRefinementLoop

            self._notify("Arquitecto v2: clasificando complejidad del proyecto...", "LOG", {"phase": "master_contract"})
            classifier = ProjectComplexityClassifier()
            assessment = classifier.classify(project.blueprint)
            self._notify(f"Arquitecto v2: proyecto clasificado como '{assessment.level.value}'", "LOG", {"complexity": assessment.level.value})

            goal_tree = self._build_goal_tree_from_blueprint(project.blueprint)
            topology = getattr(project, "topology", None) or {}

            active_skills = [{"name": s} if isinstance(s, str) else s for s in (project.skills or [])]
            auditor = ContractAuditor(goal_tree=goal_tree, topology=topology)
            execute_kwargs = dict(
                blueprint=project.blueprint,
                complexity=assessment.level,
                topology=topology,
                active_skills=active_skills,
                active_profile={},
                goal_tree=goal_tree,
            )

            self._notify("Arquitecto v2: generando contrato con Gemini (Fases)...", "LOG", {"phase": "master_contract", "driver": "gemini"})
            
            gemini_result = None
            gemini_exception_reason = None
            try:
                gemini_result = await ContractRefinementLoop(
                    architect=Architect(self.gemini),
                    auditor=auditor,
                    max_attempts=3,
                    notify_fn=self._notify,
                ).execute(**execute_kwargs)
            except Exception as gemini_exc:
                import traceback as _tb
                gemini_exception_reason = f"{type(gemini_exc).__name__}: {gemini_exc}"
                self._notify(f"Arquitecto v2 [Gemini]: excepción", "HEALTH_WARN", {"error": gemini_exception_reason})

            if gemini_result is not None and gemini_result.status in ("approved", "approved_with_warnings"):
                self._save_master_contract(project, gemini_result, assessment)
                return

            self._notify("Arquitecto v2: Gemini falló, usando skeleton", "HEALTH_WARN", {"phase": "master_contract"})
            from kernel.intelligence.architect import generate_skeleton_contract
            skeleton = generate_skeleton_contract(project.blueprint, topology)
            from kernel.orchestration.contract_refinement_loop import RefinementResult
            fallback_result = RefinementResult(status="approved_with_warnings", contract=skeleton, attempts=[], failed_reason="Skeleton fallback")
            self._save_master_contract(project, fallback_result, assessment)

        except Exception as e:
            self._notify(f"Arquitecto v2 falló: {e}", "PIPELINE_ERROR", {})
            raise

"""

pattern = re.compile(re.escape(start_marker) + r".*?(?=" + re.escape(end_marker) + ")", re.DOTALL)
new_content = pattern.sub(new_func, content)

with open("kernel/orchestration/phase_mixin.py", "w", encoding="utf-8") as f:
    f.write(new_content)
