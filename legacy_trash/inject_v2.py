import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

v2_injection = """        self._apply_intensity_level(project)
        self._apply_project_type(project)
        self._apply_capability_packs(project)

        # ── SODA V2 PIPELINE ──────────────────────────────────────────
        def save_file_wrapper(filepath: str, file_content: str):
            src_dir = project.workspace / "source"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / filepath).write_text(file_content, encoding="utf-8")
            
        def notify_wrapper(event_type: str, message: str):
            self._notify(message, event_type, {"project_id": project.id})

        async def ask_user_wrapper(question: str) -> str:
            from kernel.communication.user_interaction import get_gateway
            gw = get_gateway()
            return await gw.ask(question, notify_fn=self._notify)

        try:
            # --- CAPA 0: WISDOM ---
            notify_wrapper("PHASE_START", "Capa 0: Analizando requerimientos...")
            from kernel.orchestration.layer0_wisdom import resolve_ambiguities
            final_description = await resolve_ambiguities(
                user_prompt=description,
                gemini_driver=self.gemini,
                ask_user_fn=ask_user_wrapper,
                notify_fn=notify_wrapper
            )
            project.description = final_description
            self._save_state(project)

            # --- CAPA 1: GÉNESIS ---
            notify_wrapper("PHASE_START", "Iniciando SODA V2: Generando Contrato Génesis...")
            from kernel.orchestration.genesis import generate_root_contract
            root_contract = await generate_root_contract(
                user_description=project.description,
                active_skills=project.skills or [],
                gemini_driver=self.gemini,
                notify_fn=notify_wrapper
            )
            (project.workspace / "soda_v2_root.json").write_text(root_contract.model_dump_json(indent=2), encoding="utf-8")
            
            # --- MOTOR RECURSIVO ---
            from kernel.orchestration.recursive_engine import SodaRecursiveEngine
            lang = "python"
            skills_str = " ".join([s if isinstance(s, str) else str(s) for s in (project.skills or [])]).lower()
            if any(x in skills_str for x in ["typescript", "nextjs", "react", "angular"]):
                lang = "typescript"
            elif "nodejs" in skills_str:
                lang = "javascript"
            elif "golang" in skills_str:
                lang = "go"
            elif "rust" in skills_str:
                lang = "rust"
                
            engine = SodaRecursiveEngine(
                gemini_driver=self.gemini,
                ollama_driver=self.ollama,
                stack_language=lang,
                notify_fn=notify_wrapper,
                save_file_fn=save_file_wrapper
            )
            
            notify_wrapper("PHASE_START", "Fase de Arquitectura: Descomposición Recursiva")
            all_contracts = await engine.decompose_tree(root_contract)
            
            import json
            tree_dump = {k: v.model_dump() for k, v in all_contracts.items()}
            (project.workspace / "soda_v2_tree.json").write_text(json.dumps(tree_dump, indent=2), encoding="utf-8")
            
            notify_wrapper("PHASE_START", "Fase de Desarrollo: Ejecución Bottom-Up")
            await engine.execute_bottom_up(all_contracts)
            
            # --- ADAPTADORES LEGACY ---
            from kernel.utils.v2_adapters import generate_legacy_artifacts
            generate_legacy_artifacts(tree_dump, project.skills or [], str(project.workspace))
            
            notify_wrapper("SUCCESS", "¡SODA V2 ha completado el proyecto exitosamente!")
            project.state = ProjectState.DONE
            self._save_state(project)
            return project
            
        except Exception as e:
            import traceback as _tb
            error_msg = f"Colapso en el Motor V2: {str(e)}"
            notify_wrapper("ERROR", error_msg)
            print(f"\\n[ERROR FATAL V2] {error_msg}\\n{_tb.format_exc()}")
            project.state = ProjectState.FAILED
            self._save_state(project)
            return project
        # ──────────────────────────────────────────────────────────────
"""

# Replace the initial setup of run() with the V2 injection, returning early.
pattern = re.compile(r'        self\._apply_intensity_level\(project\)\n        self\._apply_project_type\(project\)\n        self\._apply_capability_packs\(project\)', re.DOTALL)
content = pattern.sub(v2_injection, content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
