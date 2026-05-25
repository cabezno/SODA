import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

start_marker = '        try:\n            self._current_phase = "capabilities"'
end_marker = '        return project\n'

new_code = """        # ── SODA V2 PIPELINE ──────────────────────────────────────────
        def save_file_wrapper(filepath: str, file_content: str):
            # Guardamos en la carpeta 'source' del workspace
            src_dir = project.workspace / "source"
            src_dir.mkdir(parents=True, exist_ok=True)
            (src_dir / filepath).write_text(file_content, encoding="utf-8")
            
        def notify_wrapper(event_type: str, message: str):
            self._notify(message, event_type, {"project_id": project.id})

        try:
            notify_wrapper("PHASE_START", "Iniciando SODA V2: Generando Contrato Génesis...")
            
            # 1. Génesis
            from kernel.orchestration.genesis import generate_root_contract
            root_contract = await generate_root_contract(
                user_description=description,
                active_skills=project.skills or [],
                gemini_driver=self.gemini,
                notify_fn=notify_wrapper
            )
            
            # Guardar estado inicial para debug
            (project.workspace / "soda_v2_root.json").write_text(root_contract.model_dump_json(indent=2), encoding="utf-8")
            
            # 2. Instanciar Motor Recursivo
            from kernel.orchestration.recursive_engine import SodaRecursiveEngine
            
            # Infer tech stack from skills
            lang = "python"
            skills_str = " ".join([s if isinstance(s, str) else str(s) for s in (project.skills or [])]).lower()
            if "typescript" in skills_str or "nextjs" in skills_str or "react" in skills_str or "angular" in skills_str:
                lang = "typescript"
            elif "nodejs" in skills_str:
                lang = "javascript"
            elif "golang" in skills_str:
                lang = "go"
            elif "rust" in skills_str:
                lang = "rust"
            elif "java" in skills_str:
                lang = "java"
            elif "csharp" in skills_str:
                lang = "csharp"
            elif "php" in skills_str:
                lang = "php"
                
            engine = SodaRecursiveEngine(
                gemini_driver=self.gemini,
                ollama_driver=self.ollama,
                stack_language=lang,
                notify_fn=notify_wrapper,
                save_file_fn=save_file_wrapper
            )
            
            # 3. Descomposición Recursiva (Top-Down)
            notify_wrapper("PHASE_START", "Fase de Arquitectura: Descomposición Recursiva")
            all_contracts = await engine.decompose_tree(root_contract)
            
            # Guardar el árbol completo
            import json
            tree_dump = {k: v.model_dump() for k, v in all_contracts.items()}
            (project.workspace / "soda_v2_tree.json").write_text(json.dumps(tree_dump, indent=2), encoding="utf-8")
            
            # 4. Filtrar Nodos Atómicos (hecho internamente por execute_bottom_up, pero aquí lo mencionamos)
            # 5. Ejecución (Bottom-Up)
            notify_wrapper("PHASE_START", "Fase de Desarrollo: Ejecución Bottom-Up")
            await engine.execute_bottom_up(all_contracts)
            
            notify_wrapper("SUCCESS", "¡SODA V2 ha completado el proyecto exitosamente!")
            project.state = ProjectState.DONE
            self._save_state(project)
            
        except Exception as e:
            # Manejo de Errores Críticos (Evita que el servidor crashee)
            import traceback as _tb
            error_msg = f"Colapso en el Motor V2: {str(e)}"
            notify_wrapper("ERROR", error_msg)
            print(f"\\n[ERROR FATAL V2] {error_msg}\\n{_tb.format_exc()}")
            project.state = ProjectState.FAILED
            self._save_state(project)
            # raise e  # Descomentar si deseamos que relance, por ahora solo logueamos.

        return project
"""

pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
new_content = pattern.sub(new_code, content, count=1)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(new_content)
