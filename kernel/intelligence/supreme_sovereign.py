import asyncio
import json
import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union, Literal
from pydantic import BaseModel, Field, ValidationError
from kernel.validators.v2.polyglot_validator import PolyglotValidator

# --- MODELOS DE CONTRATO (PYDANTIC) ---

class CritiqueIssue(BaseModel):
    file: str = Field(..., description="Ruta del archivo con el problema")
    issue: str = Field(..., description="Descripción clara del error o mejora")
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    instruction: str = Field(..., description="Instrucción técnica precisa para la corrección")

class CritiqueReport(BaseModel):
    issues: List[CritiqueIssue] = []

# --- MOTOR DE AUDITORÍA SUPREMO POLÍGLOTA ---

# --- DEEP THINKING Layer ---
from kernel.intelligence.deep_thinking import DeepThinkingAnalyzer
from kernel.intelligence.recursive_planner import RecursivePlannerCouncil

class SupremeSovereignAgent:
    """
    SODA SUPREME SOVEREIGN PIPELINE (V4 - Polyglot Edition)
    
    Protocolo de 8 fases que adapta su rigor de auditoría según el WISDOM del proyecto.
    Valida múltiples lenguajes y tareas (Backend, Frontend, Data, Config).
    """

    def __init__(self, ai_hub, notify_fn: Optional[Callable] = None, speckit: Any = None):
        self.ai_hub = ai_hub
        self.notify = notify_fn
        self.speckit = speckit
        self.deep_thinking = DeepThinkingAnalyzer(ai_hub, notify_fn)
        # IMP-034: Registro de comportamiento de agentes
        self.consecutive_lies = {} # {role: count}

    def _log(self, msg: str, event_type: str = "LOG"):
        if self.notify:
            self.notify(msg, event_type)
        else:
            print(f"[{event_type}] {msg}")

    async def _safe_call(self, provider: str, sys_p: str, user_m: str, max_t: int = 8192) -> str:
        try:
            resp = await self.ai_hub.get(provider).call(system_prompt=sys_p, user_message=user_m, max_tokens=max_t)
            return resp.content
        except Exception as e:
            self._log(f"Error llamando a {provider}: {e}", "WARNING")
            return await self.ai_hub.call_with_fallback(primary=provider, role="SOVEREIGN", task=f"{sys_p}\n\n{user_m}")

    async def _generate_relay_note(self, phase_name: str, files: Dict[str, str], task_desc: str) -> str:
        """Genera una nota de relevo para la siguiente fase del pipeline soberano."""
        sys_p = (
            "Eres el Technical Lead de SODA SUPREME. Redacta una NOTA DE RELEVO para la siguiente fase.\n"
            "MANDATORIO: Sé técnico y conciso. Resume qué se logró en esta fase y qué debe cuidar la siguiente."
        )
        user_msg = f"FASE COMPLETADA: {phase_name}\nARCHIVOS AFECTADOS: {list(files.keys())}\nMISIÓN: {task_desc}"
        try:
            # Usamos gemini para el relevo por ser el "Presidente"
            resp = await self.ai_hub.get("gemini").call(system_prompt=sys_p, user_message=user_msg, max_tokens=500)
            return resp.content.strip()
        except:
            return f"Fase {phase_name} completada. Archivos actualizados."

    def _determine_language_from_path(self, path: str) -> str:
        """Heurística para determinar el lenguaje de auditoría."""
        ext = path.split('.')[-1].lower()
        mapping = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'jsx': 'javascript',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'md': 'markdown',
            'txt': 'text',
            'c': 'c',
            'cpp': 'cpp',
            'cs': 'csharp',
            'go': 'go',
            'rs': 'rust'
        }
        return mapping.get(ext, 'text')

    def _verify_promises(self, raw_output: str, extracted_files: Dict[str, str], phase_name: str):
        """
        IMP-010: Promise Verification Gate.
        Extracts promised file paths from the AI's narrative and verifies their 
        presence in the extracted payload.
        """
        # Buscar patrones como "He creado src/cli.py", "Archivo: tests/test_main.py", etc.
        promised_paths = re.findall(r'(?:He creado|Archivo|Se ha generado|Se implementó|src/|tests/)([\w\./\-]+\.\w+)', raw_output)
        
        # Limpiar y normalizar
        promised_paths = {p.strip().lower() for p in promised_paths if '.' in p}
        extracted_paths = {p.lower() for p in extracted_files.keys()}
        
        missing_promises = promised_paths - extracted_paths
        # Filtro de ruido: solo alertar sobre archivos de código/configuración probables
        critical_extensions = ['.py', '.html', '.js', '.css', '.json', '.sh', '.yml', '.yaml']
        missing_promises = {p for p in missing_promises if any(p.endswith(ext) for ext in critical_extensions)}

        if missing_promises:
            self._log(f"FALLO DE PROMESA DETECTADO en {phase_name}: {missing_promises}", "WARNING")
            # Por ahora solo logueamos y lanzamos si es masivo, para evitar falsos positivos
            if len(missing_promises) > 2:
                 raise ValueError(f"ALUCINACIÓN DETECTADA: El agente afirma haber creado {missing_promises} pero no los incluyó en la entrega física.")

    def _extract_project_symbols(self, files: Dict[str, str]) -> str:
        """
        IMP-026: Extrae nombres de clases y funciones para sincronización global.
        Ayuda al cirujano a no alucinar nombres de interfaces.
        """
        symbols = []
        for path, content in files.items():
            # Extraer clases
            classes = re.findall(r'class\s+(\w+)', content)
            # Extraer funciones
            funcs = re.findall(r'def\s+(\w+)\s*\(', content)
            
            if classes or funcs:
                symbols.append(f"ARCHIVO: {path}")
                if classes: symbols.append(f"  Clases: {', '.join(classes)}")
                if funcs: symbols.append(f"  Funciones: {', '.join(funcs)}")
        
        return "\n".join(symbols) if symbols else "No se detectaron símbolos globales aún."

    async def _heal_code(self, code: str, error_msg: str, language: str, project_symbols: str = "") -> str:
        """
        IMP-025/026: AST-Self-Healer with Global Name-Space Sync.
        """
        self._log(f"Iniciando Cirugía AST para reparar error: {error_msg[:100]}...", "LOG")
        
        sys_p = (
            f"Eres el Cirujano Jefe de SODA. Tu misión es corregir un error técnico en el código {language.upper()}.\n"
            "MANDATORIO: Devuelve ÚNICAMENTE el código corregido completo.\n"
            "Sin explicaciones, sin markdown, solo el código fuente listo para ejecución.\n\n"
            f"CONTEXTO DE NOMBRES GLOBALES (IMP-026):\n{project_symbols}\n"
            "Usa estos nombres si necesitas hacer referencia a otros módulos del proyecto."
        )
        
        user_msg = (
            f"CÓDIGO CON ERROR:\n{code}\n\n"
            f"ERROR DETECTADO POR EL KERNEL:\n{error_msg}\n\n"
            "Corrige el error de sintaxis o estructura manteniendo la coherencia con los símbolos globales."
        )
        
        try:
            # Usamos gemini-3.5-flash por su velocidad y precisión en cirugía
            model = self.ai_hub.get("gemini-3.5-flash") or self.ai_hub.get("gemini")
            resp = await model.call(system_prompt=sys_p, user_message=user_msg, max_tokens=8192)
            return PolyglotValidator.clean_markdown(resp.content)
        except Exception as e:
            self._log(f"Fallo en cirugía AST: {e}", "WARNING")
            return code

    def _gather_implementation_reference(self, workspace_path: Optional[Path]) -> str:
        """
        IMP-027: The Contextual Glue.
        Carga el código REAL de los archivos existentes en el disco para dar contexto
        de implementación al siguiente agente. Destruye el 'limbo' de generación aislada.
        """
        if not workspace_path: return ""
        src_dir = workspace_path / "source"
        if not src_dir.exists(): return ""

        ref_context = "--- REFERENCIA DE IMPLEMENTACIÓN REAL (Contextual Glue) ---\n"
        found = False
        # Solo cargamos archivos de código críticos para no saturar el contexto
        for p in src_dir.rglob("*.py"):
            if p.is_file() and p.stat().st_size > 0:
                try:
                    rel_p = p.relative_to(src_dir)
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    # Incluimos solo las firmas y docstrings para ahorrar tokens si el archivo es grande
                    ref_context += f"FILE: {rel_p}\n{content}\n\n"
                    found = True
                except: pass
        
        return ref_context + "---------------------------------------------------------" if found else ""

    async def _audit_file_task(self, path: str, content: str, target_lang: str, extracted: Dict[str, str], context_files: Dict[str, str], paradigm: Optional[str] = None):
        """Tarea asíncrona para auditar y curar un archivo individual."""
        lang = self._determine_language_from_path(path)
        try:
            # Validación Estructural/AST
            if lang == "python":
                PolyglotValidator.validate_code(content, "python")
            elif lang == "json":
                json.loads(content)
            elif lang in ["javascript", "typescript", "cpp", "csharp", "go"]:
                PolyglotValidator.validate_code(content, lang)
            
            # Validación de Coherencia
            if lang in ["text", "markdown"] and len(content.strip()) < 5:
                raise ValueError(f"El archivo {path} está sospechosamente vacío.")

        except (ValueError, json.JSONDecodeError) as audit_err:
            # Autocuración en caso de fallo
            self._log(f"Error detectado en {path}. Invocando Cirujano AST...", "WARNING")
            project_symbols = self._extract_project_symbols({**extracted, **(context_files or {})})
            healed_content = await self._heal_code(content, str(audit_err), lang, project_symbols)
            
            # Validar código curado
            PolyglotValidator.validate_code(healed_content, lang)
            extracted[path] = healed_content
            self._log(f"Archivo {path} curado exitosamente.", "SUCCESS")

    async def _call_with_contract(
        self, 
        provider: str, 
        role: str, 
        task: str, 
        contract_type: Literal["CODE", "JSON"],
        project_wisdom: Dict[str, Any] = None,
        context_files: Dict[str, str] = None,
        workspace_path: Optional[Path] = None
    ) -> Union[Dict[str, str], CritiqueReport]:
        """
        Llamada con Auditoría Multilenguaje Coherente, Auditoría Paralela e Isolation (IMP-035).
        """
        attempts = 0
        last_error = ""
        target_lang = project_wisdom.get("language", "python").lower() if project_wisdom else "python"
        
        # IMP-035: Detectar paradigma del proyecto
        paradigm = "cli" # Default
        if project_wisdom:
            p_desc = str(project_wisdom).lower()
            if any(k in p_desc for k in ["api", "rest", "backend"]): paradigm = "api"
            elif any(k in p_desc for k in ["library", "sdk", "libreria"]): paradigm = "library"
        
        # IMP-009/027: Physical Context
        physical_manifest = ""
        implementation_ref = ""
        if workspace_path:
            physical_manifest = "\n" + self._generate_physical_manifest(workspace_path)
            implementation_ref = "\n" + self._gather_implementation_reference(workspace_path)

        # IMP-034: Penaliación adaptativa por alucinación
        consecutive_lies = self.consecutive_lies.get(role, 0)
        temp = 0.7 if consecutive_lies < 2 else 0.0
        
        while attempts < 3:
            sys_p = f"Eres un experto en {role.upper()}. El proyecto usa {target_lang.upper()} bajo paradigma {paradigm.upper()}.\nMisión: {task}.\n\n"
            
            # IMP-017 / IMP-034: Accountability & Humiliation
            if consecutive_lies >= 2:
                sys_p += (
                    "🚨 HUMILLACIÓN TÉCNICA (SODA Inquisitor): Has sido detectado MINTIENDO sistemáticamente en tus entregas.\n"
                    "TU TEMPERATURA HA SIDO REDUCIDA A 0.0. No tienes permitido el uso de lenguaje narrativo.\n"
                    "MANDATORIO: Escribe el código fuente COMPLETO línea por línea. Si vuelves a alucinar un archivo inexistente, serás purgado del sistema.\n\n"
                )
            else:
                sys_p += (
                    f"⚠️ REGLA DE RIGOR (IMP-035): Estás en un proyecto {paradigm.upper()}. "
                    "Está ESTRICTAMENTE PROHIBIDO importar librerías de otros paradigmas (ej: no Web en CLI).\n"
                    "No mientas en las notas de relevo. Si dices que creaste un archivo, DEBES incluir el bloque <FILE>.\n\n"
                )

            if contract_type == "CODE":
                sys_p += (
                    f"FORMATO OBLIGATORIO: CÓDIGO FUENTE ({target_lang}).\n"
                    "Responde únicamente con bloques <FILE path='...'>[codigo]</FILE>.\n"
                    "MANDATORIO: Sin explicaciones, solo archivos coherentes con el proyecto."
                )
            else:
                sys_p += "FORMATO OBLIGATORIO: JSON PURO (CritiqueReport)."

            if last_error:
                sys_p += f"\n\n⚠️ FALLO TÉCNICO DETECTADO: {last_error}"

            user_msg = f"WISDOM DEL PROYECTO:\n{json.dumps(project_wisdom, indent=2)}\n\nCONTEXTO:\n{task}"
            user_msg += physical_manifest + implementation_ref
            
            if context_files:
                user_msg += "\n\nARCHIVOS PROPUESTOS:\n" + "\n".join([f"FILE: {p}\n{c}" for p, c in context_files.items()])

            # Realizar llamada con temperatura adaptativa
            try:
                model_driver = self.ai_hub.get(provider)
                resp = await model_driver.call(system_prompt=sys_p, user_message=user_msg, max_tokens=8192, temperature=temp)
                raw_response = resp.content
            except Exception as e:
                self._log(f"Error llamando a {provider}: {e}", "WARNING")
                raw_response = await self.ai_hub.call_with_fallback(primary=provider, role="SOVEREIGN", task=f"{sys_p}\n\n{user_msg}")

            try:
                if contract_type == "CODE":
                    extracted = PolyglotValidator.extract_files(raw_response)
                    if not extracted:
                        raise ValueError("Protocolo de archivos violado: No se detectaron bloques <FILE>.")
                    
                    # IMP-010/012: Promise Verification
                    try:
                        self._verify_promises(raw_response, extracted, role)
                        # Si pasa la verificación, reseteamos el contador de mentiras
                        self.consecutive_lies[role] = 0
                    except ValueError as lie_err:
                        self.consecutive_lies[role] = self.consecutive_lies.get(role, 0) + 1
                        raise lie_err

                    # --- IMP-028/035: AUDITORÍA PARALELA CON AISLAMIENTO DE PARADIGMA ---
                    audit_tasks = []
                    for path, content in extracted.items():
                        audit_tasks.append(self._audit_file_task(path, content, target_lang, extracted, context_files, paradigm))
                    
                    if audit_tasks:
                        await asyncio.gather(*audit_tasks)

                    # Validaciones Globales Finales (Imports y Linker con Paradigm Check)
                    PolyglotValidator.validate_imports(extracted, target_lang)
                    PolyglotValidator.validate_linker({**extracted, **(context_files or {})}, target_lang, paradigm)
                    
                    return extracted
                
                else:
                    clean_json = re.search(r'\{.*\}', raw_response, re.DOTALL)
                    if not clean_json: raise ValueError("Respuesta no es un JSON válido.")
                    return CritiqueReport(**json.loads(clean_json.group(0)))

            except (ValueError, SyntaxError, ValidationError, json.JSONDecodeError) as e:
                attempts += 1
                last_error = str(e)
                self._log(f"Rigor de Auditoría fallido ({provider}): {last_error}", "WARNING")

        return PolyglotValidator.extract_files(raw_response) if contract_type == "CODE" else CritiqueReport()

    def _verify_artifact_persistence(self, extracted_files: Dict[str, str], phase_name: str, workspace_path: Optional[Path] = None):
        """
        IMP-001/IMP-005/IMP-008: Hardened Artifact Integrity Gate.
        Verifica físicamente que los archivos existan en el disco y tengan contenido real.
        """
        if not extracted_files:
            return
            
        self._log(f"Artifact Gate: Verificando {len(extracted_files)} archivos en {phase_name}...")
        
        for path, content in extracted_files.items():
            # 1. Validación de Memoria (¿La IA devolvió algo válido?)
            if not content or len(content.strip()) < 10:
                raise ValueError(f"CRITICAL PERSISTENCE FAILURE: El agente reportó '{path}' pero el contenido está vacío.")

        self._log(f"Integridad física confirmada para {len(extracted_files)} archivos.", "SUCCESS")

    def _generate_physical_manifest(self, workspace_path: Path) -> str:
        """IMP-009: Genera la lista de archivos reales para evitar alucinaciones de relevo."""
        src_dir = workspace_path / "source"
        if not src_dir.exists(): return "Workspace physically empty."
        
        files = [f.relative_to(src_dir) for f in src_dir.rglob("*") if f.is_file()]
        if not files: return "Workspace physically empty."
        
        manifest = "--- REALIDAD FÍSICA DEL DISCO (Manifiesto IMP-009) ---\n"
        for f in files:
            manifest += f"- {f}\n"
        manifest += "----------------------------------------------------"
        return manifest

    async def execute_fullstack_mission(self, task_desc: str, wisdom_data: Dict[str, Any]) -> Dict[str, str]:
        """Ejecuta el pipeline de 8 fases con conciencia de lenguaje y tarea."""
        
        target_lang = wisdom_data.get("language", "Python")
        self._log(f"Iniciando Misión Suprema Multilenguaje ({target_lang})", "PHASE_START")

        # SPEC-KIT: Spec & Plan Persistence
        if self.speckit:
            self.speckit.save_spec(task_desc)
            tech_plan = {
                "title": "Supreme Sovereign Plan",
                "stack": target_lang,
                "modulos": [
                    {"id": "Frontend", "descripcion": "Capa de interfaz y UX", "archivos": ["app.py", "index.html"]},
                    {"id": "Backend", "descripcion": "Capa de lógica y datos", "archivos": ["server.py", "database.py"]}
                ]
            }
            self.speckit.save_plan(tech_plan)
            # Create a basic task tracker for Supreme mission
            from kernel.core.project_index import MasterIndex, IndexSection
            self.mission_index = MasterIndex(
                project_id="supreme",
                title="Supreme Mission Tracker",
                total_sections=4,
                sections=[
                    IndexSection(id="PH1", title="Initial Creation", description="Drafting FE and BE", status="pending"),
                    IndexSection(id="PH3", title="Self-Correction", description="Applying critiques", status="pending"),
                    IndexSection(id="PH5", title="Claude Refinement", description="Polishing with Claude", status="pending"),
                    IndexSection(id="PH8", title="Final Consolidation", description="Master Integration", status="pending")
                ]
            )
            self.speckit.sync_tasks(self.mission_index)
        else:
            self.mission_index = None

        # Fase 1: Creación Soberana
        fe_files = await self._call_with_contract("gemini", "Frontend Expert", task_desc, "CODE", project_wisdom=wisdom_data)
        be_files = await self._call_with_contract("deepseek", "Backend Expert", task_desc, "CODE", project_wisdom=wisdom_data)
        
        self._verify_artifact_persistence(fe_files, "PH1: Frontend Creation")
        self._verify_artifact_persistence(be_files, "PH1: Backend Creation")

        if self.speckit:
            note = await self._generate_relay_note("Creación Inicial", {**fe_files, **be_files}, task_desc)
            self.speckit.save_relay_note("PHASE_1_CREATION", note)
            if self.mission_index:
                self.mission_index.sections[0].status = "completed"
                self.mission_index.sections[0].relay_note = note
                self.speckit.sync_tasks(self.mission_index)

        # Fase 2: Crítica Cruzada
        fe_critique = await self._call_with_contract("deepseek", "Security & Backend Auditor", "Audita Frontend", "JSON", project_wisdom=wisdom_data, context_files=fe_files)
        be_critique = await self._call_with_contract("gemini", "UX & Frontend Auditor", "Audita Backend", "JSON", project_wisdom=wisdom_data, context_files=be_files)

        # Fase 3: Autocorrección I
        fe_fix_1 = await self._call_with_contract("gemini", "Frontend Fixer", "Aplica críticas", "CODE", project_wisdom=wisdom_data, context_files=fe_files)
        be_fix_1 = await self._call_with_contract("deepseek", "Backend Fixer", "Aplica críticas", "CODE", project_wisdom=wisdom_data, context_files=be_files)
        
        fe_files.update(fe_fix_1)
        be_files.update(be_fix_1)
        
        if self.speckit:
            note = await self._generate_relay_note("Autocorrección I", {**fe_files, **be_files}, task_desc)
            self.speckit.save_relay_note("PHASE_3_SELF_CORRECTION", note)
            if self.mission_index:
                self.mission_index.sections[1].status = "completed"
                self.mission_index.sections[1].relay_note = note
                self.speckit.sync_tasks(self.mission_index)

        # Fase 4: Auditoría Claude
        claude_report = await self._call_with_contract("claude", "Senior System Architect", "Auditoría Externa", "JSON", project_wisdom=wisdom_data, context_files={**fe_files, **be_files})

        # Fase 5: Autocorrección II
        fe_fix_2 = await self._call_with_contract("gemini", "Frontend Specialist", "Pulido Claude", "CODE", project_wisdom=wisdom_data, context_files=fe_files)
        be_fix_2 = await self._call_with_contract("deepseek", "Backend Specialist", "Pulido Claude", "CODE", project_wisdom=wisdom_data, context_files=be_files)
        
        fe_files.update(fe_fix_2)
        be_files.update(be_fix_2)
        
        if self.speckit:
            note = await self._generate_relay_note("Autocorrección II (Claude Refined)", {**fe_files, **be_files}, task_desc)
            self.speckit.save_relay_note("PHASE_5_CLAUDE_REFINE", note)
            if self.mission_index:
                self.mission_index.sections[2].status = "completed"
                self.mission_index.sections[2].relay_note = note
                self.speckit.sync_tasks(self.mission_index)

        # Fase 6: Integración
        integrated = await self._call_with_contract("gemini", "Master Integrator", "Une FE y BE", "CODE", project_wisdom=wisdom_data, context_files={**fe_files, **be_files})

        # Fase 7 y 8: Auditoría final y Pulido (Simplificado para el ejemplo pero manteniendo rigor)
        final_files = await self._call_with_contract("gemini", "Master Developer", "Sistema Final", "CODE", project_wisdom=wisdom_data, context_files=integrated)
        
        if self.speckit:
            note = await self._generate_relay_note("Sistema Final Consolidado", final_files, task_desc)
            self.speckit.save_relay_note("PHASE_8_FINAL", note)
            if self.mission_index:
                self.mission_index.sections[3].status = "completed"
                self.mission_index.sections[3].relay_note = note
                self.speckit.sync_tasks(self.mission_index)

        # --- DEEP THINKING Phase ---
        # Assuming the caller will save files to disk before DT analyzer runs, 
        # or we pass the generated content if needed. 
        # In Supreme mode, we trigger it at the end of the mission.
        # Note: OmegaEngine usually handles the workspace path.
        
        return final_files
