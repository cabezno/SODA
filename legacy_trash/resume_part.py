    async def resume(self, project_id: str) -> "Project":
        """Reanuda un proyecto SODA V2 desde su estado guardado."""
        self.perf_tracker.reset()
        project = self._project_from_disk(project_id)
        self._active_project = project

        print(f"\n{'='*55}")
        print(f"SODA — RESUME: {project.id}")
        print(f"Estado guardado: {project.state.value}")
        print(f"{'='*55}")

        self._notify(
            f"Reanudando proyecto '{project.id}' desde estado: {project.state.value}",
            "RESUME_START",
            {"project_id": project.id, "state": project.state.value},
        )

        # --- SODA V2 RESUME LOGIC ---
        v2_tree_path = project.workspace / "soda_v2_tree.json"
        if v2_tree_path.exists():
            try:
                import json
                from kernel.core.models_v2 import SodaContract
                from kernel.orchestration.recursive_engine import SodaRecursiveEngine
                
                tree_data = json.loads(v2_tree_path.read_text(encoding="utf-8"))
                contracts_pool = {k: SodaContract(**v) for k, v in tree_data.items()}
                
                # Inferencia de lenguaje
                lang = "python"
                skills_str = " ".join([s if isinstance(s, str) else str(s) for s in (project.skills or [])]).lower()
                if any(x in skills_str for x in ["typescript", "nextjs", "react", "angular"]):
                    lang = "typescript"
                elif "nodejs" in skills_str:
                    lang = "javascript"
                
                def save_file_wrapper(filepath: str, file_content: str):
                    src_dir = project.workspace / "source"
                    src_dir.mkdir(parents=True, exist_ok=True)
                    (src_dir / filepath).write_text(file_content, encoding="utf-8")
                    
                def notify_wrapper(event_type: str, message: str):
                    self._notify(message, event_type, {"project_id": project.id})

                engine = SodaRecursiveEngine(
                    gemini_driver=self.gemini,
                    ollama_driver=self.ollama,
                    stack_language=lang,
                    notify_fn=notify_wrapper,
                    save_file_fn=save_file_wrapper
                )

                # 1. ¿Necesita descomposición?
                pending_decomp = [c for c in contracts_pool.values() if not c.is_atomic and c.status == "PENDING_DECOMPOSITION"]
                if pending_decomp:
                    self._notify("Reanudando desde Descomposición...", "LOG", {"project_id": project.id})
                    root = next((c for c in contracts_pool.values() if c.level == 0), None)
                    if root:
                        contracts_pool = await engine.decompose_tree(root)
                        tree_dump = {k: v.model_dump() for k, v in contracts_pool.items()}
                        v2_tree_path.write_text(json.dumps(tree_dump, indent=2), encoding="utf-8")
                
                # 2. Ejecutar Bottom-Up
                atomic_pending = [c for c in contracts_pool.values() if c.is_atomic and c.status != "COMPLETED"]
                if atomic_pending:
                    self._notify("Reanudando ejecución Bottom-Up...", "LOG", {"project_id": project.id})
                    await engine.execute_bottom_up(contracts_pool)
                    
                    # Guardar estado final y adaptadores
                    tree_dump = {k: v.model_dump() for k, v in contracts_pool.items()}
                    v2_tree_path.write_text(json.dumps(tree_dump, indent=2), encoding="utf-8")
                    
                    from kernel.utils.v2_adapters import generate_legacy_artifacts
                    generate_legacy_artifacts(tree_dump, project.skills or [], str(project.workspace))
                
                project.state = ProjectState.DONE
                self._save_state(project)
                self._notify("Reanudación V2 completada.", "SUCCESS", {"project_id": project.id})
                return project

            except Exception as e:
                import traceback
                self._notify(f"Error crítico en reanudación V2: {str(e)}", "PIPELINE_ERROR", {"project_id": project.id})
                print(f"\n[ERROR FATAL V2 RESUME] {str(e)}\n{traceback.format_exc()}")
                project.state = ProjectState.FAILED
                self._save_state(project)
                return project
                
        # If no V2 tree, it's a legacy V1 project
        self._notify("Este proyecto fue creado con V1. La reanudación legacy está deshabilitada.", "ERROR", {"project_id": project.id})
        return project


if __name__ == "__main__":
    import asyncio
    orchestrator = SodaOrchestrator()
    asyncio.run(orchestrator.run(
        "Quiero una app web CRUD simple para gestionar una lista de tareas: "
        "crear, leer, actualizar y eliminar tareas con titulo, descripcion y estado."
    ))
