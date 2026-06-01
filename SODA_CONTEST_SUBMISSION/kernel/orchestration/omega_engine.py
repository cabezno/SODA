import asyncio
import json
import re
import os
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

from kernel.core.models_v2 import SodaContract, ContractStatus
from kernel.validators.v2.polyglot_validator import PolyglotValidator

from kernel.orchestration.mission_intelligence import MissionProfile, MissionCriticality
from kernel.intelligence.council_agent import CouncilAgent
from kernel.intelligence.symbolic_conformance import SymbolicConformanceVerifier

# --- SPEC-KIT Integration ---
from kernel.orchestration.speckit_manager import SpecKitManager

# --- DEEP THINKING Layer ---
from kernel.intelligence.deep_thinking import DeepThinkingAnalyzer

# --- SODA FUSION: New Execution Engine Imports ---
from kernel.execution_engine.blueprint import ProjectBlueprint, TaskStatus
from kernel.execution_engine.sandbox.manager import DockerSandbox
from kernel.execution_engine.autogen_runner import SODAAutogenRunner
from kernel.execution_engine.adapter import translate_to_blueprint

# --- RC3 Architecture Imports ---
from kernel.core.project_index import MasterIndex, IndexSection
from kernel.intelligence.recursive_council import RecursiveCouncilAgent
from kernel.intelligence.supreme_sovereign import SupremeSovereignAgent

class OmegaEngine:
    """
    SODA OMEGA: Morphological Refinement Engine.
    Dynamically adapts AI roles and parameters based on project complexity.
    RC3 VERSION: Sequential Append-Only Council with Indexing.
    """

    def __init__(
        self,
        gemini_driver,
        ai_hub,
        notify_fn: Optional[Callable] = None,
        workspace: Optional[Path] = None,
        mission_profile: Optional[MissionProfile] = None
    ):
        self.gemini = gemini_driver
        self.ai_hub = ai_hub
        self.notify = notify_fn
        self.workspace = workspace
        self.profile = mission_profile
        self.council = CouncilAgent(ai_hub, notify_fn) # Legacy support
        self.rc3 = RecursiveCouncilAgent(ai_hub, notify_fn) # NEW

        # Deep Thinking Analyzer Layer
        self.deep_thinking = DeepThinkingAnalyzer(ai_hub, notify_fn)

        # Spec-Kit Artifact Manager
        if self.workspace:
            # We assume workspace is projects/<id>/workspace
            self.speckit = SpecKitManager(self.workspace.parent if "workspace" in str(self.workspace).lower() else self.workspace)
        else:
            self.speckit = None

        self.supreme = SupremeSovereignAgent(ai_hub, notify_fn, self.speckit) # SUPREME V3
        self.conformance = SymbolicConformanceVerifier()
        
        # Lineup dinámico
        if self.profile:
            lineup = self.profile.suggested_lineup
            self.architect = ai_hub.get(lineup.get("architect")) or gemini_driver
            self.developer = ai_hub.get(lineup.get("developer")) or gemini_driver
            self.auditor = ai_hub.get(lineup.get("auditor")) or gemini_driver
            self.polisher = ai_hub.get(lineup.get("polisher")) or gemini_driver
        else:
            self.architect = gemini_driver
            self.developer = gemini_driver
            self.auditor = ai_hub.get("deepseek") or gemini_driver
            self.polisher = ai_hub.get("claude") or gemini_driver

    def _log(self, event_type: str, msg: str):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[{event_type}] {msg}")

    async def _validate_semantic_alignment(self, spec: str, plan: Dict[str, Any]) -> bool:
        """
        IMP-002: Semantic Alignment Gate.
        Verifies that the Technical Plan is consistent with the Specification.
        Prevents cases like 'CLI mission' resulting in 'Web architecture'.
        """
        self._log("LOG", "[JUEZ] Validando alineación semántica Spec -> Plan...")
        
        sys_p = (
            "Eres el Auditor de Arquitectura de SODA.\n"
            "Tu misión es detectar si el PLAN TÉCNICO se ha desviado de la ESPECIFICACIÓN original.\n"
            "REGLAS:\n"
            "1. Si la Spec pide CLI y el Plan menciona HTML, CSS, JavaScript o Servidores Web, el plan está DESALINEADO.\n"
            "2. Si la Spec pide una API y el Plan no menciona endpoints o autenticación, el plan está INCOMPLETO.\n"
            "SALIDA: Un JSON puro: {\"is_aligned\": bool, \"reason\": \"explicación corta\"}"
        )
        
        user_msg = f"ESPECIFICACIÓN:\n{spec}\n\nPLAN TÉCNICO PROPUESTO:\n{json.dumps(plan, indent=2)}"
        
        try:
            resp = await self.gemini.call(system_prompt=sys_p, user_message=user_msg, response_format="json")
            data = json.loads(re.search(r'\{.*\}', resp.content, re.DOTALL).group(0))
            
            if not data.get("is_aligned", True):
                self._log("ERROR", f"DESALINEACIÓN DETECTADA: {data.get('reason')}")
                return False
            
            self._log("SUCCESS", "Alineación semántica Spec -> Plan verificada.")
            return True
        except Exception as e:
            self._log("WARNING", f"Error en validación semántica: {e}. Procediendo con precaución.")
            return True

    def _generate_workspace_manifest(self) -> str:
        """
        IMP-009: SHA256 Workspace State Manifest.
        Generates a real-time list of physical files to destroy AI illusions.
        """
        if not self.workspace:
            return "No workspace available."
            
        src_dir = self.workspace / "source"
        if not src_dir.exists():
            return "Workspace empty (source/ not found)."

        manifest = "--- MANIFIESTO DE ESTADO REAL DEL DISCO (Physical Truth) ---\n"
        files = list(src_dir.rglob("*"))
        found_any = False
        for f in files:
            if f.is_file():
                rel_p = f.relative_to(src_dir)
                size = f.stat().st_size
                manifest += f"- [FILE] {rel_p} ({size} bytes)\n"
                found_any = True
        
        if not found_any:
            manifest += "(El disco está físicamente vacío)\n"
            
        manifest += "---------------------------------------------------------"
        return manifest

    def _update_state_ledger(self, new_files: Dict[str, str]):
        """
        IMP-011: State-Preservation Ledger.
        Maintains a cumulative record of all files created to prevent 'Software Shrinking'.
        """
        if not self.workspace: return
        
        ledger_path = self.workspace / ".soda_manifest.json"
        ledger = {}
        if ledger_path.exists():
            try:
                ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            except: ledger = {}
            
        # Actualizar el ledger con los nuevos archivos (sin borrar los anteriores)
        for path in new_files.keys():
            ledger[path] = {
                "timestamp": time.time(),
                "status": "active"
            }
            
        ledger_path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
        self._log("LOG", f"[LEDGER] Manifiesto actualizado. Total archivos registrados: {len(ledger)}")

    def _persist_to_disk(self, files: Dict[str, str]):
        """Persiste físicamente los archivos generados en el disco del host."""
        if not self.workspace: return
        
        src_dir = self.workspace / "source"
        src_dir.mkdir(parents=True, exist_ok=True)
        
        self._log("LOG", f"[PERSISTENCE] Escribiendo {len(files)} archivos en {src_dir}...")
        
        for path, content in files.items():
            dest = src_dir / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Limpiar posibles bloques markdown
            clean_content = content.strip()
            if clean_content.startswith("```"):
                lines = clean_content.splitlines()
                if len(lines) > 1:
                    clean_content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

            dest.write_text(clean_content, encoding="utf-8")
        
        self._log("SUCCESS", "Archivos persistidos físicamente en el disco.")

    def _sync_plan_to_reality(self, delivered_files: Dict[str, str], master_index: MasterIndex):
        """
        IMP-038: Sincronización Bidireccional de Plan.
        Re-escribe el plan.md para que coincida exactamente con lo entregado.
        """
        if not self.speckit: return
        
        self._log("LOG", "[SYNC] Sincronizando plan.md con la realidad del código...")
        
        delivered_paths = list(delivered_files.keys())
        
        # Actualizamos el plan técnico para Spec-Kit
        sync_plan = {
            "title": f"{master_index.title} (As-Built)",
            "modulos": [
                {
                    "id": "Software_Entregado",
                    "descripcion": "Arquitectura real consolidada tras auditoría",
                    "archivos": delivered_paths
                }
            ],
            "stack": "Python / CLI / SQLite (Realidad Física)"
        }
        
        self.speckit.save_plan(sync_plan)
        self._log("SUCCESS", "Plan técnico sincronizado con éxito.")

    async def run_omega_pipeline(self, description: str, project_id: str) -> Dict[str, str]:
        self._log("PHASE_START", f"Iniciando SODA RC3 (Recursive Council) para: {project_id}")
        
        # SPEC-KIT: 1. Constitution Phase
        if self.speckit:
            self.speckit.initialize_constitution()
            self._log("LOG", "[SPEC-KIT] Constitución del proyecto inicializada.")

        # RESULT HOLDER
        final_result_files = {}

        # SODA SUPREME: Si la complejidad es alta o el perfil es software completo, usar el pipeline soberano
        if self.profile and self.profile.complexity_score >= 5:
            self._log("LOG", "Activando MODO SUPREMO SOBERANO por complejidad detectada.")
            final_result_files = await self.supreme.execute_fullstack_mission(description, {})
        else:
            # 1. Fase de Indexación (RC3 Consensuado)
            master_index = await self._fase_indexacion(description, project_id)
            self._log("LOG", f"Índice Maestro generado: {master_index.total_sections} secciones.")
            
            # --- IMP-031: RECURSIVE PLANNING COUNCIL (RPC) ---
            if self.profile and self.profile.use_council:
                self._log("LOG", "[RPC] Iniciando Negociación de Plan Atómico por complejidad detectada.")
                from kernel.intelligence.recursive_planner import RecursivePlannerCouncil
                planner_council = RecursivePlannerCouncil(self.ai_hub, self.notify)
                
                # Contexto para la planificación
                plan_context = f"PROYECTO: {project_id}\nWISDOM: {description}\nINDEX: {json.dumps(master_index.dict())}"
                atomic_plan = await planner_council.negotiate_plan(description, plan_context)
                
                # SODA evoluciona el MasterIndex con el plan atómico negociado
                # (En esta versión, el plan atómico se guarda como referencia técnica)
                if self.workspace:
                    (self.workspace / "atomic_plan_consensuado.json").write_text(json.dumps(atomic_plan, indent=2), encoding="utf-8")
                    self._log("SUCCESS", "[RPC] Plan Atómico Consensuado persistido en disco.")

            # SPEC-KIT: 2. Spec & Plan Persistence
            if self.speckit:
                self.speckit.save_spec(description)
                tech_plan = {
                    "title": master_index.title,
                    "modulos": [{"id": s.id, "descripcion": s.description, "archivos": s.target_files} for s in master_index.sections]
                }
                
            # --- SEMANTIC ALIGNMENT GATE (IMP-002 / IMP-013) ---
            is_aligned = await self._validate_semantic_alignment(description, tech_plan)
            if not is_aligned:
                self._log("ERROR", "PLAN RECHAZADO: Desalineación semántica crítica detectada. Abortando para corrección.")
                # Elevamos error duro para forzar replanificación real o intervención
                raise ValueError("Architectural Mismatch: The plan does not align with the mission requirements (e.g. Web plan for CLI mission).")
            
            self.speckit.save_plan(tech_plan)
            self.speckit.sync_tasks(master_index)

            # PERSISTENCIA DEL ÍNDICE PARA LA UI
            if self.workspace:
                index_path = self.workspace / "master_index.json"
                index_path.write_text(json.dumps(master_index.dict(), indent=2), encoding="utf-8")

            # 2. Ejecución Paginada
            final_code = {}
            action_history = []
            sections = master_index.get_flat_sections()
            
            for section in sections:
                current_context = f"--- CONTEXTO ---\nOBJETIVO: {description}\nSECCIÓN: {section.title}\n"
                # IMP-009: Inject Physical Truth Manifest
                current_context += self._generate_workspace_manifest() + "\n"
                
                chunk_files = await self.rc3.execute_chunk(
                    task_desc=f"{section.title}: {section.description}",
                    context=current_context + (self.speckit.get_all_relay_notes() if self.speckit else ""),
                    target_files=section.target_files
                )

                if self.speckit:
                    section.relay_note = await self._generate_relay_note(section.title, chunk_files, description)
                    # IMP-010/012: The Lie Detector (Cumulative Promise Matcher)
                    self.supreme._verify_promises(section.relay_note, chunk_files, f"Sección {section.id}")
                    
                    self.speckit.save_relay_note(section.id, section.relay_note)
                    section.status = "completed"
                    self.speckit.sync_tasks(master_index)

                final_code.update(chunk_files)
            
            # 3. Limpieza Estructural (JANITOR)
            blueprint_simulado = {"modulos": [{"id": s.id, "archivos": s.target_files} for s in sections]}
            # Recuperar archivos del Ledger que podrían haber sido omitidos por el último agente
            ledger_files = self._read_workspace_files()
            final_code.update(ledger_files)
            final_result_files = self._fase_limpieza_janitor(final_code, blueprint_simulado)
            # IMP-038: Sync plan.md with reality
            self._sync_plan_to_reality(final_result_files, master_index)

        # --- PERSISTENCIA ATÓMICA PRE-AUDITORÍA ---
        # Paso crítico: Escribimos al disco ANTES de que el Artifact Gate chequee el estado real.
        self._persist_to_disk(final_result_files)
        
        # --- DEEP THINKING Phase (Universal) ---
        if self.deep_thinking and self.workspace:
            # We must ensure the workspace points to the project root, not the 'source' subfolder
            project_root = self.workspace.parent if "workspace" in str(self.workspace).lower() else self.workspace
            await self.deep_thinking.generate_forensic_report(
                project_path=project_root,
                mission_desc=description
            )

        # --- ARTIFACT GATE (IMP-005 / SUPREME RIGOR) ---
        if self.workspace and final_result_files:
            src_dir = self.workspace / "source"
            physical_files = list(src_dir.rglob("*"))
            # [REFINADO] Permitir __init__.py vacíos pero exigir contenido en el resto
            physical_files = [f for f in physical_files if f.is_file() and (f.stat().st_size > 50 or f.name == "__init__.py")]
            
            if len(physical_files) < (len(final_result_files) * 0.5):
                self._log("ERROR", f"BRECHA DE INTEGRIDAD: Se esperaban {len(final_result_files)} archivos pero solo hay {len(physical_files)} válidos.")
                raise RuntimeError("SODA_INQUISITION_FAILED: El sistema detectó una entrega fantasma. Código no persistido.")
            else:
                self._log("SUCCESS", f"Artifact Gate superado: {len(physical_files)} archivos de ingeniería real verificados.")

        self._log("SUCCESS", "SODA Pipeline completado con Auditoría Deep Thinking.")
        return final_result_files

    async def _execute_atomic_plan_council(self, atomic_plan: List[Dict[str, Any]], description: str, project_id: str) -> Dict[str, str]:
        """
        IMP-032: Ejecución Granular por Pasos.
        Recorre el plan atómico negociado y ejecuta cada paso mediante el pipeline soberano.
        """
        self._log("PHASE_START", f"Iniciando Ejecución de Plan Atómico ({len(atomic_plan)} pasos)")
        accumulated_files = {}

        for step in atomic_plan:
            step_id = step.get("id", "step")
            task = step.get("task", "Tarea sin descripción")
            target_files = step.get("files", [])
            
            self._log("LOG", f"--- EJECUTANDO PASO: {step_id} ---")
            self._log("LOG", f"Tarea: {task}")
            
            # El contexto incluye los archivos acumulados hasta ahora (Contextual Glue)
            step_wisdom = {
                "step_id": step_id,
                "task": task,
                "target_files": target_files,
                "project_id": project_id,
                "language": "python"
            }
            
            # Ejecutamos la micro-misión vía Supreme Sovereign
            step_result = await self.supreme.execute_fullstack_mission(task, step_wisdom)
            
            # Fusión y Persistencia
            accumulated_files.update(step_result)
            self._update_state_ledger(step_result)
            
            self._log("SUCCESS", f"Paso {step_id} completado y verificado físicamente.")

        return accumulated_files

    async def _generate_relay_note(self, section_title: str, files: Dict[str, str], global_context: str) -> str:
        """
        Generates a 'Relay Note' (Nota de Relevo) to pass technical context to the next task.
        """
        sys_p = (
            "Eres el Technical Lead de SODA. Tu misión es redactar una NOTA DE RELEVO para el siguiente desarrollador.\n"
            "MANDATORIO: Sé ultra-conciso. Describe decisiones técnicas clave, cambios en nombres de variables/archivos y advertencias de integración.\n"
            "SALIDA: Un bloque de texto Markdown con puntos clave."
        )
        
        file_summary = ", ".join(list(files.keys()))
        user_msg = (
            f"SECCIÓN RECIÉN COMPLETADA: {section_title}\n"
            f"ARCHIVOS GENERADOS: {file_summary}\n"
            f"CONTEXTO GLOBAL: {global_context[:500]}...\n\n"
            "Redacta el relevo técnico para que la siguiente IA no cometa errores de inconsistencia."
        )
        
        try:
            resp = await self.gemini.call(system_prompt=sys_p, user_message=user_msg, max_tokens=1000)
            return resp.content.strip()
        except Exception as e:
            self._log("WARNING", f"Error al generar nota de relevo: {e}")
            return "No se pudo generar nota de relevo. Mantener precaución con la integración."

    async def _judicial_safe_merge(
        self, 
        path: str, 
        current_content: str, 
        proposed_content: str, 
        mission_context: str,
        section_context: str
    ) -> str:
        """
        Gemini como Juez Supremo decide si acepta una propuesta de mejora sobre un archivo existente.
        Protege contra errores de 'EXHAUSTED', alucinaciones o rupturas de contrato.
        """
        # 1. Filtro Heurístico de Seguridad (Zero-Failure)
        forbidden_patterns = ["ERROR:EXHAUSTED", "API limit reached", "No se pudo generar"]
        if any(p in proposed_content for p in forbidden_patterns):
            self._log("WARNING", f"[JUEZ] Rechazada propuesta corrupta para {path} (Patrón de error detectado).")
            return current_content

        # 2. Arbitraje de Inteligencia
        sys_p = (
            "Eres el JUEZ SUPREMO de SODA. Tu palabra es la ley final de integración de código.\n"
            "Misión: Comparar el código ACTUAL de un archivo con una PROPUESTA DE MEJORA generada en una nueva sección.\n"
            "REGLAS:\n"
            "1. Si la propuesta rompe la funcionalidad, contiene errores de sintaxis o es inferior al original, RECHÁZALA.\n"
            "2. Si la propuesta agrega valor, integra nuevas funciones de la sección actual o mejora la robustez, ACÉPTALA.\n"
            "3. Puedes decidir FUSIONAR ambas versiones si ves que ambas tienen partes valiosas.\n"
            "4. Si la propuesta es basura (mensajes de error, placeholders, truncada), RECHÁZALA de inmediato.\n"
            "SALIDA: Devuelve únicamente el código final que debe quedar en el archivo."
        )

        user_msg = (
            f"ARCHIVO: {path}\n"
            f"MISIÓN GLOBAL: {mission_context}\n"
            f"SECCIÓN ACTUAL: {section_context}\n\n"
            f"--- CÓDIGO ACTUAL ---\n{current_content}\n\n"
            f"--- PROPUESTA DE MEJORA ---\n{proposed_content}\n\n"
            "Decide la versión final y devuélvela íntegra."
        )

        try:
            resp = await self.gemini.call(system_prompt=sys_p, user_message=user_msg)
            # Limpiar por si la IA agregó explicaciones o markdown
            judged_content = PolyglotValidator.clean_markdown(resp.content)

            if not judged_content or len(judged_content) < 10: # Fallback si el juez devuelve algo vacío o muy corto
                self._log("WARNING", f"[JUEZ] Respuesta del juez inválida para {path}. Manteniendo original.")
                return current_content

            self._log("SUCCESS", f"[JUEZ] Decisión tomada para {path}. Integración completada.")
            return judged_content

        except Exception as e:
            self._log("ERROR", f"[JUEZ] Error durante el arbitraje de {path}: {e}. Manteniendo original por seguridad.")
            return current_content

    async def _fase_indexacion(self, description: str, project_id: str) -> MasterIndex:
        self._log("LOG", "[RC3] Fase 1: Indexación del Proyecto")
        
        # IMP-006: Inject Mandatory Guardrails into the Indexing Phase
        description += (
            "\n\n⚠️ REGLA DE ARQUITECTURA (SODA Guardrail): "
            "Si este proyecto implica indexación o búsqueda de archivos, "
            "DEBES incluir obligatoriamente una lista negra de exclusión: "
            "['.git', 'node_modules', '.venv', '__pycache__', '.DS_Store']."
        )
        
        task_desc = (
            "Eres el Gran Indexador de SODA. Tu misión es descomponer un requerimiento en un ÍNDICE MAESTRO.\n"
            "REGLA DE OUTPUT_LENGTH: Cada sección no debe exceder los 4000 tokens de salida. Si un tema es largo, divídelo en SUB-ÍNDICES (2.1, 2.2).\n"
            "REGLA DE SEPARACIÓN DE TESTS (IMP-036): No incluyas los tests unitarios en la misma sección que la lógica de negocio.\n"
            "MANDATORIO: Crea una SECCIÓN FINAL exclusiva para los tests unitarios (ej: '7.0: Suite de Pruebas Unitarias').\n"
            "SALIDA: Un JSON puro con 'title', 'total_sections', y 'sections' (lista de {id, title, description, target_files})."
        )
        
        try:
            # Ejecutar ciclo de consenso para el ÍNDICE inicial
            index_files = await self.rc3.execute_chunk(
                task_desc=f"Generar índice para: {description[:100]}...",
                context=f"Instrucción: {task_desc}",
                target_files=["master_index.json"]
            )
            
            index_content = index_files.get("master_index.json", "{}")
            match = re.search(r'\{.*\}', index_content, re.DOTALL)
            if not match:
                raise ValueError("No se pudo encontrar un JSON válido en la respuesta del indexador.")
                
            data = json.loads(match.group(0))
            master_index = MasterIndex(project_id=project_id, **data)
        except Exception as e:
            self._log("ERROR", f"Fallo crítico en indexación RC3: {e}. Generando índice de emergencia...")
            # Fallback a un índice mínimo para no detener el pipeline
            master_index = MasterIndex(
                project_id=project_id,
                title=f"Proyecto {project_id} (Modo Emergencia)",
                total_sections=1,
                sections=[
                    IndexSection(
                        id="1.0",
                        title="Implementación Base",
                        description=f"Implementación completa basada en: {description[:100]}...",
                        target_files=["main.py", "requirements.txt", "README.md"]
                    )
                ]
            )

        # --- REFINAMIENTO RECURSIVO DEL ÍNDICE ---
        # Si alguna sección es demasiado genérica o compleja, pedimos subdivisión.
        refined_sections = []
        for section in master_index.sections:
            if self._is_section_too_complex(section):
                self._log("LOG", f"[RC3] Refinando sección compleja: {section.title}")
                sub_sections = await self._subdivide_section(section, description)
                section.sub_indices = sub_sections
            refined_sections.append(section)
        
        master_index.sections = refined_sections
        return master_index

    def _is_section_too_complex(self, section: IndexSection) -> bool:
        """Determina si una sección necesita subdivisión basado en heurísticas."""
        # Si la descripción es muy larga (> 500 chars) o tiene muchas palabras clave de 'core'
        complexity_keywords = ["core", "orchestrator", "engine", "complex", "management", "system"]
        word_count = len(section.description.split())
        has_keywords = any(k in section.description.lower() for k in complexity_keywords)
        
        return word_count > 60 or (word_count > 30 and has_keywords)

    async def _subdivide_section(self, section: IndexSection, mission_context: str) -> List[IndexSection]:
        """Llama a Gemini para dividir una sección madre en sub-índices atómicos."""
        sys_p = (
            "Eres el Micro-Arquitecto de SODA. Tu misión es dividir una sección de proyecto compleja en sub-secciones atómicas.\n"
            "REGLA DE ATOMICIDAD: Cada sub-sección debe poder implementarse en un solo paso de IA (< 4000 tokens).\n"
            "SALIDA: Un JSON puro con una lista 'sub_sections' conteniendo objetos {id, title, description, target_files}."
        )
        
        user_msg = (
            f"MISIÓN GLOBAL: {mission_context}\n"
            f"SECCIÓN A DIVIDIR: {section.title} ({section.id})\n"
            f"DESCRIPCIÓN: {section.description}\n"
            f"ARCHIVOS OBJETIVO: {section.target_files}\n"
        )
        
        try:
            resp = await self.gemini.call(system_prompt=sys_p, user_message=user_msg, response_format="json")
            data = json.loads(re.search(r'\{.*\}', resp.content, re.DOTALL).group(0))
            sub_raw = data.get("sub_sections", [])
            return [IndexSection(**s) for s in sub_raw]
        except Exception as e:
            self._log("WARNING", f"Error al subdividir sección {section.id}: {e}. Se mantendrá original.")
            return []

    def _fase_limpieza_janitor(self, files: Dict[str, str], blueprint_data: Any) -> Dict[str, str]:
        """
        IMP-015: Anti-Garbage Collection Janitor.
        Preserves files registered in the State Ledger even if the current agent omitted them.
        """
        self._log("LOG", "[JANITOR] Fase 6: Limpieza Estructural Protegida (Anti-GC)")
        
        # 1. Archivos planeados actualmente
        modulos = blueprint_data.get("modulos", [])
        archivos_blueprint = set()
        for mod in modulos:
            for path in mod.get("archivos", []):
                archivos_blueprint.add(path.replace("\\", "/").strip("/"))
        
        # 2. Archivos registrados históricamente en el Ledger (IMP-011)
        ledger_files = set()
        if self.workspace:
            ledger_path = self.workspace / ".soda_manifest.json"
            if ledger_path.exists():
                try:
                    ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
                    ledger_files = {p.replace("\\", "/").strip("/") for p in ledger_data.keys()}
                except: pass

        # 3. Archivos 'Inmunes'
        inmunes = {"requirements.txt", "README.md", "main.py", ".env", "setup.py"}
        
        # Unificamos el 'Set de Verdad'
        safe_set = archivos_blueprint.union(ledger_files).union(inmunes)
        
        cleaned_files = {}
        redundant_count = 0
        
        for path, content in files.items():
            norm_path = path.replace("\\", "/").strip("/")
            if norm_path in safe_set or norm_path == "main.py":
                cleaned_files[path] = content
            else:
                self._log("WARNING", f"[JANITOR] Eliminando archivo redundante no registrado: {path}")
                redundant_count += 1
                
        self._log("SUCCESS", f"[JANITOR] Limpieza completada. {len(cleaned_files)} archivos preservados ({redundant_count} eliminados).")
        return cleaned_files

    async def _fase_desarrollo_fusion(self, description: str, blueprint_data: Any, tests: Any):
        self._log("LOG", "[FUSION] Iniciando fase de desarrollo con AutoGen y Sandbox...")
        
        # A. Traducir blueprint de SODA-PROJECT a SODAA Task Graph
        fusion_bp = translate_to_blueprint("SODA_FUSION_Project", blueprint_data)
        
        # B. Preparar Sandbox (Workspace apuntando al source del proyecto)
        src_dir = self.workspace / "source"
        src_dir.mkdir(parents=True, exist_ok=True)
        sandbox = DockerSandbox(workspace_dir=str(src_dir))
        
        # C. Configuración de LLM para AutoGen
        # SODA FUSION prefiere usar el modelo local para el picado de código (más rápido y sin cuotas)
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        if "/v1" not in ollama_url:
            ollama_url = f"{ollama_url.rstrip('/')}/v1"
            
        config_list = [
            {
                "model": "qwen2.5-coder:14b",
                "base_url": ollama_url,
                "api_key": "NULL"
            },
            {
                "model": "qwen2.5-coder:7b",
                "base_url": ollama_url,
                "api_key": "NULL"
            }
        ]
        
        # Añadir Gemini solo si hay key y no estamos en modo offline
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            # SODA OMEGA puede usar Gemini como fallback de alta calidad
            config_list.append({
                "model": "gemini-1.5-pro",
                "api_key": gemini_key,
                "api_type": "google"
            })
            config_list.append({
                "model": "gemini-1.5-flash",
                "api_key": gemini_key,
                "api_type": "google"
            })

        llm_config = {
            "config_list": config_list,
            "cache_seed": 42,
            "timeout": 120,
            "temperature": 0.1
        }

        # D. Ejecutar Orquestador AutoGen
        try:
            sandbox.start()
            runner = SODAAutogenRunner(
                blueprint=fusion_bp,
                sandbox=sandbox,
                llm_config=llm_config,
                notify_fn=self.notify
            )
            await runner.execute_blueprint()
            self._log("SUCCESS", "[FUSION] Desarrollo vía AutoGen finalizado.")
        finally:
            sandbox.stop()

    def _read_workspace_files(self) -> Dict[str, str]:
        """Lee los archivos generados en el workspace de 'source/'."""
        files = {}
        src_dir = self.workspace / "source"
        for path in src_dir.rglob("*"):
            if path.is_file():
                relative_path = path.relative_to(src_dir)
                try:
                    files[str(relative_path)] = path.read_text(encoding="utf-8")
                except Exception: pass
        return files

    async def _verify_and_repair_conformance(self, files: Dict[str, str], blueprint: Any):
        self._log("LOG", "[OMEGA] Iniciando Auditoría de Conformidad Simbólica...")
        
        # Extract modules using recursive finder
        modules = self.conformance.find_modules(blueprint)
        if not modules:
            self._log("WARNING", "[OMEGA] No se encontraron definiciones de módulos con interfaces para validación simbólica.")
            return

        all_ok = True
        for mod in modules:
            report = self.conformance.verify_module(mod, files)
            if not report.is_conformant:
                all_ok = False
                self._log("ERROR", f"[OMEGA] Módulo '{mod.get('id')}' no cumple el contrato. Reparando...")
                await self._repair_module(mod, files, report)
        
        if all_ok:
            self._log("SUCCESS", "[OMEGA] Conformidad simbólica total verificada.")

    async def _repair_module(self, mod: dict, files: Dict[str, str], report: Any):
        sys_p = (
            "Eres el Ingeniero de Reparación de SODA. El código generado NO CUMPLE el contrato arquitectónico.\n"
            "Tu única misión es corregir el archivo para que coincida EXACTAMENTE con las interfaces solicitadas.\n"
            "MANDATORIO: No cambies la lógica interna si es correcta, solo ajusta nombres de funciones y parámetros."
        )
        error_msg = f"ERROR DE CONFORMIDAD:\nMissing: {report.missing_interfaces}\nMismatches: {report.parameter_mismatches}\n"
        
        # Identify files for this module
        mod_id = mod.get('id')
        mod_files = {p: c for p, c in files.items() if mod_id in p.lower() or any(f in p for f in mod.get('archivos', []))}
        
        combined = "\n".join([f"FILE: {p}\n{c}" for p, c in mod_files.items()])
        user_msg = f"CONTRATO: {json.dumps(mod)}\n{error_msg}\nCÓDIGO ACTUAL:\n{combined}"
        
        resp = await self.developer.call(system_prompt=sys_p, user_message=user_msg)
        extracted = PolyglotValidator.extract_files(resp.content)
        if extracted:
            files.update(extracted)
            self._log("LOG", f"[OMEGA] Módulo '{mod_id}' reparado simbólicamente.")

    async def _fase_verificacion_proposito(self, files: Dict[str, str], original_desc: str, tests: Any) -> Dict[str, str]:
        self._log("LOG", "[OMEGA] Fase 5: Verificación de Propósito")
        combined_code = "\n\n".join([f"### ARCHIVO: {p}\n{c}" for p, c in files.items()])
        
        sys_p = (
            "Eres el Juez de Calidad Final. Tu misión es asegurar que el producto CUMPLE lo que el cliente pidió.\n"
            "REGLA: Si el código es funcional y cumple el requerimiento, responde 'VERIFIED'.\n"
            "Si faltan funcionalidades críticas o hay errores lógicos, responde con los archivos CORREGIDOS usando <FILE path='...'> tags.\n"
            "No seas complaciente. Si el usuario pidió un sistema de archivos y no hay endpoint de subida, RECHAZA y CORRIGE."
        )
        user_msg = f"REQUERIMIENTO ORIGINAL: {original_desc}\nTESTS ESPERADOS: {json.dumps(tests)}\nCÓDIGO FINAL:\n{combined_code}"
        
        if self.profile and self.profile.use_council:
            content = await self.council.convene(
                task=user_msg,
                system_context=sys_p,
                council_members=["gemini", "claude", "deepseek"],
                chairman="gemini",
                response_format="text"
            )
        else:
            resp = await self.gemini.call(system_prompt=sys_p, user_message=user_msg, max_tokens=8192)
            content = resp.content
        
        if "VERIFIED" in content.upper() and "<FILE" not in content:
            self._log("SUCCESS", "[OMEGA] Verificación exitosa: El producto cumple con el propósito.")
            return files
        else:
            extracted = PolyglotValidator.extract_files(content)
            if extracted:
                self._log("WARNING", f"[OMEGA] El Juez detectó omisiones. Aplicando {len(extracted)} correcciones de propósito.")
                files.update(extracted)
            return files

    async def _fase_concepcion(self, description: str):
        self._log("LOG", f"[OMEGA] Fase 1: Arquitectura")
        
        rigor = "Nivel KERNEL" if self.profile and self.profile.criticality == MissionCriticality.KERNEL else "Estándar"
        sys_p = (
            f"Eres el Arquitecto Jefe de SODA. Rigor solicitado: {rigor}.\n"
            "REGLA DE MINIMALISMO EXTREMO: Prioriza la simplicidad. Diseña entre 1 y 5 módulos máximo para requerimientos estándar. Evita microservicios innecesarios.\n"
            "REGLA DE LÍMITE DE DOMINIO: Prohibido diseñar módulos de DevOps, Infraestructura o Kubernetes. SODA se enfoca exclusivamente en Código de Aplicación.\n"
            "SALIDA: Un JSON puro y válido con:\n"
            "1. 'blueprint': Un objeto que contenga una lista 'modulos'. Cada módulo debe tener: 'id', 'descripcion', 'archivos' (lista de rutas) e 'interfaces' (lista de objetos {name, params, is_async, description}).\n"
            "2. 'tests': Suite de pruebas funcionales.\n"
            "3. 'stack': Stack tecnológico elegido.\n"
            "IMPORTANTE: No uses elipsis. Debe ser parseable."
        )
        
        last_error = ""
        for attempt in range(3):
            try:
                msg = f"REQUERIMIENTOS: {description}"
                if last_error:
                    msg += f"\n\nERROR PREVIO DE PARSEO: {last_error}\nPOR FAVOR, CORRIGE EL JSON Y DEVUÉLVELO COMPLETO Y VÁLIDO."
                
                if self.profile and self.profile.use_council:
                    content = await self.council.convene(
                        task=msg,
                        system_context=sys_p,
                        council_members=["gemini", "claude", "deepseek"],
                        chairman="gemini",
                        chairman_model="gemini-1.5-pro",
                        response_format="json"
                    )
                else:
                    resp = await self.architect.call(
                        system_prompt=sys_p, 
                        user_message=msg, 
                        response_format="json",
                        temperature=0.1
                    )
                    content = resp.content

                content = re.search(r'\{.*\}', content, re.DOTALL)
                content = content.group(0) if content else "{}"
                data = json.loads(content)
                return data.get("blueprint"), data.get("tests")
            except Exception as e:
                last_error = str(e)
                if attempt == 2: raise e
                self._log("WARNING", f"Intento {attempt+1} falló al parsear arquitectura, reintentando... ({e})")

    async def _fase_desarrollo_base(self, description: str, blueprint: Any, tests: Any):
        self._log("LOG", f"[OMEGA] Fase 2: Implementación ({self.developer.target_model if hasattr(self.developer, 'target_model') else 'Gemini'})")
        max_t = self.profile.max_tokens if self.profile else 4096
        
        sys_p = (
            "Eres un Senior Developer. COMPLETITUD TOTAL.\n"
            "Usa <FILE path='...'> tags. NO elipsis. Código funcional 100%."
        )
        user_msg = f"BLUEPRINT: {json.dumps(blueprint)}\nTESTS: {json.dumps(tests)}\nDESCRIPTION: {description}"
        resp = await self.developer.call(
            system_prompt=sys_p, 
            user_message=user_msg, 
            max_tokens=max_t,
            temperature=self.profile.temperature if self.profile else 0.2
        )
        extracted = PolyglotValidator.extract_files(resp.content)
        self._log("LOG", f"[OMEGA] Archivos extraídos: {len(extracted)}")
        return extracted

    async def _fase_auditoria_deepseek(self, files: Dict[str, str], blueprint: Any, tests: Any):
        self._log("LOG", f"[OMEGA] Fase 3: Auditoría Dinámica ({self.auditor.target_model if hasattr(self.auditor, 'target_model') else 'DeepSeek'})")
        
        # Solo auditar archivos que podrían tener errores — no reescribir todo
        auditor_type = "HACKER / SECURITY" if "security" in (self.profile.required_auditors if self.profile else []) else "CODE REVIEWER"
        sys_p = (
            f"Eres un {auditor_type}. Revisa el código en busca de errores según el rigor {self.profile.criticality if self.profile else 'MEDIUM'}.\n"
            "SOLO responde con parches para los archivos que tengan errores. Usa el formato:\n"
            "ARCHIVO: <path>\nERROR: <descripción>\nPARCHE: <diff o código corregido>\n\n"
            "Si el código está bien, NO devuelvas nada para ese archivo. No repitas archivos sin cambios."
        )
        
        # Procesar archivos de a grupos pequeños para evitar sobrecarga de contexto
        changed_files = {}
        file_list = list(files.items())
        for i in range(0, len(file_list), 5):
            batch = dict(file_list[i:i+5])
            batch_code = "\n\n".join([f"### ARCHIVO: {p}\n{c}" for p, c in batch.items()])
            user_msg = f"REVISA ESTOS ARCHIVOS:\n{batch_code}\nBLUEPRINT: {json.dumps(blueprint)}"
            try:
                resp = await self.auditor.call(
                    system_prompt=sys_p,
                    user_message=user_msg,
                    max_tokens=self.profile.max_tokens if self.profile else 4096,
                    temperature=0.0
                )
                from kernel.validators.v2.polyglot_validator import PolyglotValidator
                extracted = PolyglotValidator.extract_files(resp.content)
                if extracted:
                    changed_files.update(extracted)
                    self._log("LOG", f"[OMEGA] Auditoría encontró {len(extracted)} archivos con errores en lote {i//5 + 1}.")
            except Exception as e:
                self._log("WARNING", f"[OMEGA] Auditoría falló para lote {i//5 + 1}: {e}")
        
        if changed_files:
            self._log("LOG", f"[OMEGA] Aplicando {len(changed_files)} correcciones de auditoría.")
            files.update(changed_files)
        else:
            self._log("SUCCESS", "[OMEGA] Auditoría: código limpio, sin correcciones necesarias.")
        return files

    async def _fase_consolidacion_claude(self, files: Dict[str, str], blueprint: Any, tests: Any):
        self._log("LOG", f"[OMEGA] Fase 4: Consolidación ({self.polisher.target_model if hasattr(self.polisher, 'target_model') else 'Polisher'})")
        
        # Claude NO reescribe todo — solo consolida archivos con problemas
        sys_p = (
            "Eres el Release Engineer. Revisa si los archivos tienen problemas de integración entre sí.\n"
            "MANDATORIO: Solo devuelve archivos que tengan errores de integración o inconsistencias.\n"
            "Si el código está correcto e integrado, NO devuelvas nada. Usa <FILE path='...'> tags solo cuando haya un error real."
        )
        
        # Agrupar archivos por módulo y pasar solo los que tengan dependencias compartidas
        changed_files = {}
        file_list = list(files.items())
        for i in range(0, len(file_list), 8):
            batch = dict(file_list[i:i+8])
            batch_code = "\n\n".join([f"### ARCHIVO: {p}\n{c}" for p, c in batch.items()])
            user_msg = f"REVISA ESTOS ARCHIVOS ({len(batch)} archivos):\n{batch_code}\nTESTS: {json.dumps(tests)}"
            try:
                resp = await self.polisher.call(
                    system_prompt=sys_p,
                    user_message=user_msg,
                    max_tokens=self.profile.max_tokens if self.profile else 8192
                )
                extracted = PolyglotValidator.extract_files(resp.content)
                if extracted:
                    changed_files.update(extracted)
                    self._log("LOG", f"[OMEGA] Claude corrigió {len(extracted)} archivos en lote {i//8 + 1}.")
            except Exception as e:
                self._log("WARNING", f"[OMEGA] Claude falló para lote {i//8 + 1}: {e}")
        
        if changed_files:
            self._log("LOG", f"[OMEGA] Aplicando {len(changed_files)} correcciones de consolidación.")
            files.update(changed_files)
        else:
            self._log("SUCCESS", "[OMEGA] Consolidación: código ya integrado, sin cambios.")
        return files
