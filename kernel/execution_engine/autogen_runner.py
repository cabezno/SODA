import autogen
from pathlib import Path
from typing import Any, Dict, Optional, Callable
from kernel.execution_engine.sandbox.manager import DockerSandbox
from kernel.execution_engine.blueprint import ProjectBlueprint, TaskStatus, Task
from kernel.utils.blackbox_logger import SodaLogger

class SODAAutogenRunner:
    def __init__(
        self, 
        blueprint: ProjectBlueprint, 
        sandbox: DockerSandbox, 
        llm_config: Dict[str, Any],
        notify_fn: Optional[Callable] = None,
        blackbox: Optional[SodaLogger] = None
    ):
        self.blueprint = blueprint
        self.sandbox = sandbox
        self.notify = notify_fn or (lambda msg, ev="LOG": print(f"[{ev}] {msg}"))
        self.blackbox = blackbox

        # 1. Agente Arquitecto (Define la estrategia basándose en el Blueprint)
        self.architect = autogen.AssistantAgent(
            name="Architect",
            llm_config=llm_config,
            system_message="""Eres el Arquitecto de SODA FUSION. 
            Tu objetivo es descomponer tareas del Blueprint en especificaciones técnicas detalladas.
            Solo puedes avanzar si el código anterior ha sido validado exitosamente en el Sandbox."""
        )

        # 2. Agente Desarrollador (Escribe el código)
        self.developer = autogen.AssistantAgent(
            name="Developer",
            llm_config=llm_config,
            system_message="""Eres el MOTOR DE IMPLEMENTACIÓN de SODA FUSION. 
            Tu única misión es entregar CÓDIGO REAL Y COMPLETO basado en un objetivo común.
            
            REGLAS DE ORO:
            1. COLABORACIÓN EN CASCADA: Si ya existe código previo, CONSTRÚYELO ENCIMA. No borres trabajo funcional.
            2. INTEGRIDAD DE RUTAS: Tienes PROHIBIDO inventar rutas. Usa exactamente las rutas del prompt.
            3. PROHIBIDO usar placeholders. Manda archivos ÍNTEGROS.
            4. FORMATO OBLIGATORIO (EJEMPLO):
               <FILE path='folder/app.py'>
               print('Hello World')
               </FILE>
            
            Entorno: WINDOWS. Escribe 'TERMINATE' solo cuando el código esté integrado y sea funcional."""
        )

        # 3. Proxy del Sistema (Solo observador y ejecutor de comandos)
        self.executor = autogen.UserProxyAgent(
            name="SandboxProxy",
            human_input_mode="NEVER",
            code_execution_config=False, 
            is_termination_msg=lambda x: "TERMINATE" in (x.get("content") or ""),
        )

    async def execute_blueprint(self):
        self.notify("Lanzando Motor de Implementación con Guardia de Calidad...", "PHASE_START")
        
        while True:
            task = self.blueprint.get_next_runnable_task()
            if not task:
                break
            
            self.notify(f"Construyendo módulo: {task.id}", "TASK_START")
            self.blueprint.update_task_status(task.id, TaskStatus.IN_PROGRESS)
            
            try:
                # Extraer rutas obligatorias
                rutas_obligatorias = ", ".join(task.target_files) if task.target_files else "Definidas por el sistema"
                
                architect_msg = (
                    f"IMPLEMENTACIÓN REQUERIDA PARA MÓDULO: {task.id}\n"
                    f"OBJETIVO: {task.description}\n"
                    f"CONTRATO TÉCNICO: {task.contract}\n"
                    f"RUTAS OBLIGATORIAS: {rutas_obligatorias}\n\n"
                    "INSTRUCCIÓN DE COLABORACIÓN: Analiza el código previo si existe en esta sesión. "
                    "Si el código de la fase anterior es funcional, continúalo y extiéndelo. "
                    "Tu misión es que el sistema final sea una pieza ÚNICA e INTEGRADA. "
                    "Escribe los archivos usando etiquetas <FILE path='...'> respetando las rutas obligatorias."
                )
                
                # SODA FUSION: Bucle de chat con verificación de "pereza"
                current_msg = architect_msg
                for turn in range(5):
                    response = await self.executor.a_initiate_chat(
                        self.developer,
                        message=current_msg,
                        max_turns=1,
                        clear_history=False if turn > 0 else True
                    )
                    
                    last_reply = response.chat_history[-1].get("content", "")
                    
                    # ¿La IA está siendo vaga?
                    is_lazy, reason = self._check_laziness(last_reply)
                    if is_lazy:
                        self.notify(f"RECHAZO DE CALIDAD: {reason}", "WARNING")
                        current_msg = f"RECHAZADO: {reason}. Por favor, escribe la lógica REAL y COMPLETA. No acepto placeholders."
                        continue
                    
                    if "TERMINATE" in last_reply:
                        break
                    
                    current_msg = "Continúa escribiendo el resto de los archivos necesarios según el contrato."

                # EXTRACCIÓN Y RESCATE DETERMINÍSTICO
                found_files = self._rescue_complete_code()

                if found_files > 0:
                    self.blueprint.update_task_status(task.id, TaskStatus.COMPLETED)
                    self.notify(f"Módulo {task.id} verificado y guardado ({found_files} archivos).", "TASK_SUCCESS")
                else:
                    self.notify(f"Fallo Crítico: La IA no entregó código real para {task.id}.", "ERROR")
                    self.blueprint.update_task_status(task.id, TaskStatus.FAILED)
                    break

            except Exception as e:
                self.notify(f"Error en guardia de calidad: {e}", "ERROR")
                self.blueprint.update_task_status(task.id, TaskStatus.FAILED)
                break

    def _check_laziness(self, content: str) -> (bool, str):
        """Detecta si el código enviado es un placeholder."""
        content_lower = content.lower()
        lazy_markers = [
            "# placeholder", "# logic here", "# implement here", 
            "# ...", "# to be implemented", "pass #",
            "# your code here"
        ]
        
        for marker in lazy_markers:
            if marker in content_lower:
                return True, f"Se detectó el marcador de pereza '{marker}'"
        
        # Si el código es sospechosamente corto para un módulo complejo
        if len(content) < 100 and "TERMINATE" not in content:
            return True, "El código enviado es demasiado corto para ser funcional."
            
        return False, ""

    def _rescue_complete_code(self) -> int:
        """
        MOTOR DE RESCATE SODA 2.0: Extrae archivos del historial de forma quirúrgica.
        Solo confía en lo que escribió el DEVELOPER y que tiene marcas claras.
        """
        from kernel.validators.v2.polyglot_validator import PolyglotValidator
        
        # SODA FUSION: Solo nos interesa el historial entre el Proxy y el Developer
        history = self.developer.chat_messages.get(self.executor, [])
        
        best_versions = {} # path -> (length, code)

        for msg in history:
            # REGLA 1: Solo procesar mensajes que vienen del Desarrollador (IA)
            if msg.get("role") != "assistant":
                continue
                
            content = msg.get("content", "")
            if not content or "TERMINATE" in content and len(content) < 20:
                continue

            # REGLA 2: No usar el default_filename "main.py" para evitar capturar texto plano.
            # Buscamos solo bloques explícitos.
            files = PolyglotValidator.extract_files(content, default_filename="SODA_INVALID_FALLBACK")
            
            for path, code in files.items():
                if path == "SODA_INVALID_FALLBACK":
                    continue # Ignorar texto que no tiene marcas de archivo reales
                
                code_clean = code.strip()
                
                # REGLA 3: Heurística Anti-Vago / Anti-Instrucción
                is_lazy, _ = self._check_laziness(code_clean)
                if is_lazy:
                    continue
                
                # Evitar capturar accidentalmente el prompt si la IA lo repitió
                if "DISEÑO PARA" in code_clean or "IMPLEMENTACIÓN REQUERIDA" in code_clean:
                    continue

                # Guardar solo la versión más completa (más larga) de cada archivo
                if path not in best_versions or len(code_clean) > best_versions[path][0]:
                    best_versions[path] = (len(code_clean), code_clean)
        
        # Escribir las mejores versiones al disco
        written_count = 0
        for path, (length, code) in best_versions.items():
            self.notify(f"Extrayendo software: {path} ({length} bytes)", "SANDBOX_FILE")
            self.sandbox.write_file(path, code)
            written_count += 1
            
        return written_count
