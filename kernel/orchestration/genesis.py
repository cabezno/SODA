import json
from pathlib import Path
from typing import Optional, Callable, List

from kernel.core.models_v2 import SodaContract, ALLOWED_SKILLS, ContractStatus
from kernel.drivers.gemini_driver import GeminiDriver

async def generate_root_contract(
    user_description: str, 
    active_skills: List[str], 
    gemini_driver: GeminiDriver,
    notify_fn: Optional[Callable[[str, str], None]] = None,
    ai_hub: Optional[object] = None
) -> SodaContract:
    """
    Capa 1: Génesis. 
    Transforma los requerimientos del usuario en el contrato raíz (ROOT-000).
    """
    if notify_fn:
        notify_fn("Iniciando Capa 1: Génesis (Arquitecto Maestro)", "PHASE_START")

    # 1. Cargar Prompt Maestro de V2
    prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "v2" / "layer1_genesis.md"
    base_instruction = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "You are the Architect."

    # 2. Inyección de contexto
    skills_list_str = ", ".join(ALLOWED_SKILLS)
    # C1 — Surface project-specific active skills so Genesis uses the right ones
    active_hint = ""
    if active_skills:
        active_hint = (
            f"Skills detectadas para este proyecto: {', '.join(active_skills)}. "
            f"Prioriza estas en 'required_skills'.\n"
        )
    
    rules = (
        "\n## REGLAS ARQUITECTÓNICAS MANDATORIAS\n"
        "<regla_limite_dominio>: Prohibido diseñar módulos de DevOps o infraestructura. "
        "Limita el alcance exclusivamente a código de aplicación.\n"
        "<regla_minimalismo_extremo>: Aplica principio KISS. Para peticiones simples, "
        "diseña de 1 a 5 módulos máximo para no saturar al Tech Lead.\n"
    )

    context_instruction = (
        f"{base_instruction}\n\n"
        f"{rules}\n"
        f"{active_hint}"
        f"IMPORTANTE: SOLO puedes usar estas skills en 'required_skills': {skills_list_str}.\n"
    )
    user_msg = f"REQUERIMIENTO DEL USUARIO:\n{user_description}"

    # 3. SISTEMA DE CONTINUIDAD (LADDER DE ÉLITE)
    # Definimos la escalera para Génesis (Capa Crítica)
    ladder = ["gemini-3.1-pro-preview", "claude-3-5-sonnet-latest", "deepseek-chat", "gemini-3-flash-preview"]
    
    last_error = ""
    data = None

    for model_name in ladder:
        try:
            if notify_fn:
                notify_fn("LOG", f"  ↳ Intentando Génesis con {model_name}...")
            
            driver = ai_hub.get(model_name) if ai_hub else None

            # Guard: skip drivers that aren't real async callables (e.g. test MagicMocks
            # that leak into sys.modules when server restarts after pytest runs).
            import asyncio as _asyncio
            if driver and not _asyncio.iscoroutinefunction(getattr(driver, "call", None)):
                if notify_fn:
                    notify_fn("LOG", f"  Driver para {model_name} no es async — saltando.")
                continue

            if driver:
                from kernel.utils.schema_fixer import flatten_schema
                flat_schema = flatten_schema(SodaContract.model_json_schema())
                
                response = await driver.call(
                    system_prompt=context_instruction,
                    user_message=user_msg,
                    response_format="json",
                    response_schema=flat_schema,
                    model=model_name, # MEJORA: Pasamos el modelo real
                    temperature=0.4
                )
                
                if response.error_code:
                    raise RuntimeError(f"Error {response.error_code}: {response.content}")
                
                # --- DEEP THINKING CAPTURE ---
                thinking_content = ""
                # 1. Native reasoning (DeepSeek R1)
                if hasattr(response, "reasoning_content") and response.reasoning_content:
                    thinking_content += f"## NATIVE REASONING ({model_name})\n{response.reasoning_content}\n\n"
                
                # 2. Simulated reasoning (<soda_thinking>)
                import re
                thinking_match = re.search(r'<soda_thinking>([\s\S]*?)</soda_thinking>', response.content)
                if thinking_match:
                    thinking_content += f"## SODA THINKING (CoT)\n{thinking_match.group(1).strip()}\n"
                
                if thinking_content and ai_hub and hasattr(ai_hub, "blackbox") and ai_hub.blackbox:
                    try:
                        log_dir = Path(ai_hub.blackbox.workspace) / "logs"
                        log_dir.mkdir(parents=True, exist_ok=True)
                        (log_dir / "genesis_thinking.md").write_text(thinking_content, encoding="utf-8")
                        if notify_fn:
                            notify_fn("LOG", f"  [DeepThinking] Razonamiento de Génesis guardado en logs/.")
                    except Exception: pass

                # Extracción robusta de JSON
                json_match = re.search(r'\{[\s\S]*\}', response.content)
                if json_match:
                    data = json.loads(json_match.group(0))
                    
                    # 1. Mapeo de sinónimos comunes (Defensa contra alucinaciones de esquema de DeepSeek/Claude)
                    if "dynamic_persona" in data:
                        persona = data["dynamic_persona"]
                        if "role" in persona and "target_role" not in persona:
                            persona["target_role"] = persona["role"]
                        if "skills" in persona and "required_skills" not in persona:
                            persona["required_skills"] = persona["skills"]
                    
                    break # ÉXITO
            else:
                continue # Modelo no disponible en el hub, pasamos al siguiente
                
        except Exception as e:
            last_error = str(e)
            if notify_fn:
                notify_fn("WARNING", f"Fallo con {model_name}: {last_error}")
            continue

    # FALLBACK FINAL: Local (Solo si todo el Ladder de Élite falló)
    if not data:
        if notify_fn:
            notify_fn("ERROR", "Toda la escalera de Élite falló. Usando modo de supervivencia local.")
        try:
            from kernel.drivers.ollama_driver import OllamaDriver
            import re as _re_local
            ollama = OllamaDriver()
            qwen_resp = await ollama.prompt(system="Genera el contrato ROOT-000 en JSON.", user=user_msg)
            json_match = _re_local.search(r'\{[\s\S]*\}', qwen_resp)
            data = json.loads(json_match.group(0)) if json_match else None
        except Exception as e:
            raise RuntimeError(f"Génesis falló catastróficamente tras agotar todos los proveedores: {e}")

    if not data:
        raise RuntimeError("No se pudo generar el contrato raíz. Sin respuesta de IAs.")

    # Instanciación y Normalización Defensiva
    try:
        # 1. Mapeo de sinónimos comunes (Defensa contra alucinaciones de esquema de DeepSeek/Claude)
        if "role" in data.get("dynamic_persona", {}) and "target_role" not in data["dynamic_persona"]:
            data["dynamic_persona"]["target_role"] = data["dynamic_persona"]["role"]
        
        if "name" in data and "title" not in data:
            data["title"] = data["name"]
            
        if "id" in data and "contract_id" not in data:
            data["contract_id"] = data["id"]

        # 2. Forzado de inmutabilidad ROOT
        data["contract_id"] = "ROOT-000"
        data["level"] = 0
        data["is_atomic"] = False
        data["status"] = ContractStatus.PENDING_DECOMPOSITION
        
        root_contract = SodaContract(**data)
        
        if notify_fn:
            notify_fn("SUCCESS", "Capa 1 completada: Contrato Maestro validado.")
        return root_contract
        
    except Exception as e:
        if notify_fn:
             notify_fn("ERROR", f"Fallo de esquema con {model_name}. Datos recibidos: {json.dumps(data)[:200]}...")
        raise ValueError(f"El contrato generado por {model_name} no cumple el esquema: {e}")

