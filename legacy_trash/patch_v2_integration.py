import re
with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject adapters at the end of the V2 run pipeline
adapter_inject = """
            # 6. Adaptadores de Retrocompatibilidad (V1 Fallback)
            from kernel.utils.v2_adapters import generate_legacy_artifacts
            generate_legacy_artifacts(all_contracts, project.skills or [], str(project.workspace))
            
            notify_wrapper("SUCCESS", "¡SODA V2 ha completado el proyecto exitosamente!")
"""
content = content.replace('            notify_wrapper("SUCCESS", "¡SODA V2 ha completado el proyecto exitosamente!")', adapter_inject)

# 2. Patch Resume
resume_patch = """    async def resume(self, project_id: str) -> Project:
        project_dir = self.projects_dir / project_id
        if not project_dir.exists():
            raise ValueError(f"El proyecto {project_id} no existe.")

        meta_path = project_dir / "metadata.json"
        if not meta_path.exists():
            raise ValueError("No metadata.json found")

        import json
        with open(meta_path, encoding="utf-8") as f:
            data = json.load(f)

        try:
            state = ProjectState(data.get("state", "idle"))
        except ValueError:
            state = ProjectState.FAILED

        project = Project(
            id=project_id,
            description=data.get("description", ""),
            state=state,
            workspace=project_dir,
            blueprint=data.get("blueprint", {}),
            architecture=data.get("architecture", {}),
            skills=data.get("skills", []),
            profile=data.get("profile", ""),
            project_type=data.get("project_type", "software"),
            capability_packs=data.get("capability_packs", []),
            intensity_level=data.get("intensity_level", "medium"),
        )

        self._active_project = project
        self._notify(f"Reanudando proyecto {project_id}...", "START", {"project_id": project_id})

        # --- SODA V2 RESUME LOGIC ---
        v2_tree_path = project.workspace / "soda_v2_tree.json"
        if v2_tree_path.exists():
            try:
                from kernel.core.models_v2 import SodaContract
                from kernel.orchestration.recursive_engine import SodaRecursiveEngine
                
                tree_data = json.loads(v2_tree_path.read_text(encoding="utf-8"))
                contracts_pool = {k: SodaContract(**v) for k, v in tree_data.items()}
                
                # Check if we need decomposition
                pending_decomp = [c for c in contracts_pool.values() if not c.is_atomic and c.status == "PENDING_DECOMPOSITION"]
                
                lang = "python" # Simplified fallback
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

                if pending_decomp:
                    self._notify("Reanudando desde Descomposición...", "LOG", {"project_id": project.id})
                    # Pass the root to trigger decomposition
                    root = next((c for c in contracts_pool.values() if c.level == 0), None)
                    if root:
                        contracts_pool = await engine.decompose_tree(root)
                        # Save new tree
                        tree_dump = {k: v.model_dump() for k, v in contracts_pool.items()}
                        v2_tree_path.write_text(json.dumps(tree_dump, indent=2), encoding="utf-8")
                
                # Execute Bottom-Up for pending atomics
                atomic_pending = [c for c in contracts_pool.values() if c.is_atomic and c.status != "COMPLETED"]
                if atomic_pending:
                    self._notify("Reanudando ejecución Bottom-Up...", "LOG", {"project_id": project.id})
                    await engine.execute_bottom_up(contracts_pool)
                    
                    # Update tree and adapters
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
                print(f"\\n[ERROR FATAL V2 RESUME] {str(e)}\\n{traceback.format_exc()}")
                project.state = ProjectState.FAILED
                self._save_state(project)
                return project
                
        # If no V2 tree, fallback to gracefully telling user it's an old project
        self._notify("Este proyecto fue creado con V1. La reanudación legacy está deshabilitada.", "ERROR", {"project_id": project.id})
        return project"""

# Replace the whole resume method
pattern_resume = re.compile(r"    async def resume\(self, project_id: str\) -> Project:.*?(?=    async def modify\(self)", re.DOTALL)
content = pattern_resume.sub(resume_patch + "\n\n", content)

# 3. Patch Modify and Refound
modify_patch = """    async def modify(self, project: Project, user_request: str) -> dict:
        self._notify("La modificación post-generación está temporalmente deshabilitada mientras finalizamos la migración al motor SODA V2. Por favor, crea un proyecto nuevo.", "ERROR", {"project_id": project.id})
        return {"status": "error", "message": "Migración V2 en curso"}"""
pattern_modify = re.compile(r"    async def modify\(self, project: Project, user_request: str\) -> dict:.*?(?=    async def refound\(self)", re.DOTALL)
content = pattern_modify.sub(modify_patch + "\n\n", content)

refound_patch = """    async def refound(self, project: Project) -> None:
        self._notify("La refundación está temporalmente deshabilitada en V2.", "ERROR", {"project_id": project.id})"""
pattern_refound = re.compile(r"    async def refound\(self, project: Project\) -> None:.*?(?=    async def open_and_process\(self)", re.DOTALL)
content = pattern_refound.sub(refound_patch + "\n\n", content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
