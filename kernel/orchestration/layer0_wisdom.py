import json
import re
from typing import List, Optional, Callable, Any, Union
from pydantic import BaseModel, Field
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.utils.schema_fixer import flatten_schema

class WisdomQuestion(BaseModel):
    id: Optional[str] = None
    category: Optional[str] = None
    question: str

class WisdomEvaluation(BaseModel):
    is_clear_enough: bool = Field(description="True si el requerimiento es suficiente para diseñar la arquitectura sin suposiciones críticas.")
    critical_questions: List[Union[str, WisdomQuestion]] = Field(default=[], description="Lista de hasta 7 preguntas directas para resolver ambigüedades de negocio o técnicas.")


# ── Preguntas heurísticas por categoría ──────────────────────────────────────
# Se usan cuando el LLM no está disponible. No requieren ninguna IA.
_HEURISTIC_QUESTIONS: dict[str, list[str]] = {
    "native_cpp": [
        "¿La app corre en Windows, Linux o debe ser multiplataforma?",
        "¿Tiene interfaz gráfica (ventana) o es una aplicación de consola/terminal?",
        "¿Cómo se distribuye: ejecutable suelto, instalador, o build propio del usuario?",
        "¿Necesita persistir datos en disco (archivo, SQLite) o todo es en memoria?",
    ],
    "native_rust": [
        "¿Es una herramienta de línea de comandos, un servidor, o una app de escritorio?",
        "¿Tiene requisitos de performance específicos (tiempo real, baja latencia)?",
        "¿Necesita interactuar con el sistema operativo o hardware directamente?",
    ],
    "mobile": [
        "¿Es para Android, iOS o ambas plataformas?",
        "¿Necesita funcionar sin conexión a internet?",
        "¿Se conecta a un backend propio o consume APIs de terceros?",
        "¿Necesita notificaciones push o acceso a hardware (cámara, GPS)?",
    ],
    "web": [
        "¿Tiene panel de administración además de la vista de usuario final?",
        "¿Quién puede registrarse: cualquier persona, solo invitados, o es una app interna?",
        "¿Necesita pagos en línea? ¿Con qué pasarela (Stripe, MercadoPago, otra)?",
        "¿Qué datos son los más críticos de guardar? (usuarios, productos, pedidos, etc.)",
        "¿La estética es importante? ¿Tenés referencia visual o dejamos que SODA decida?",
    ],
    "api": [
        "¿Quién consume esta API: una app móvil, un frontend web, o servicios externos?",
        "¿Necesita autenticación? ¿JWT, API Key, OAuth?",
        "¿Cuántos recursos/endpoints principales tiene? (usuarios, productos, pedidos...)",
        "¿Necesita enviar emails o notificaciones?",
    ],
    "generic": [
        "¿Cuáles son las 3 funcionalidades más importantes de la app?",
        "¿Quién va a usar esta aplicación y para qué tarea concreta?",
        "¿Hay alguna tecnología específica que debamos usar o evitar?",
        "¿Tenés un plazo o restricción técnica que debamos considerar?",
    ],
}

def _select_heuristic_questions(prompt: str) -> list[str]:
    """Selecciona preguntas relevantes sin usar ningún LLM, basándose en
    palabras clave del prompt del usuario."""
    p = prompt.lower()
    if any(k in p for k in ("c++", "cpp", "cmake", "qt", "winapi", "win32", "timer c", "reloj c")):
        return _HEURISTIC_QUESTIONS["native_cpp"]
    if any(k in p for k in ("rust", "cargo", "cli", "command line", "terminal app")):
        return _HEURISTIC_QUESTIONS["native_rust"]
    if any(k in p for k in ("android", "ios", "flutter", "mobile", "celular", "movil", "móvil")):
        return _HEURISTIC_QUESTIONS["mobile"]
    if any(k in p for k in ("api", "rest", "endpoint", "microservicio", "backend", "servidor")):
        return _HEURISTIC_QUESTIONS["api"]
    if any(k in p for k in ("web", "sitio", "página", "pagina", "react", "next", "frontend", "dashboard")):
        return _HEURISTIC_QUESTIONS["web"]
    return _HEURISTIC_QUESTIONS["generic"]

async def resolve_ambiguities(
    user_prompt: str, 
    gemini_driver: GeminiDriver,
    ask_user_fn: Callable[[str], str],
    notify_fn: Optional[Callable[[str, str], None]] = None,
    model_name: Optional[str] = None,
    ai_hub: Any = None,
    rc3_agent: Any = None
) -> str:
    """
    Capa 0: Wisdom Agent RC3. 
    Analiza el prompt del usuario mediante el Consejo de los Tres y pregunta hasta que no haya ambigüedades.
    """
    AUTO_KEYWORDS = [
        "define tu", "define vos", "toma las decisiones", "decidi vos", "decidí vos",
        "autodecision", "autodecisión", "carta libre", "hazlo tu", "hazlo tú", 
        "hace lo que quieras", "hacé lo que quieras",
        "soda decide", "avanza", "avanzá", "continua", "continúa", "continuá", "proceed",
    ]

    if any(kw in user_prompt.lower() for kw in AUTO_KEYWORDS):
        if notify_fn:
            notify_fn("Modo 'Auto-Decisión' detectado en el prompt inicial. SODA tomará el mando creativo.", "SUCCESS")
        return user_prompt + "\n\nINSTRUCCIÓN DE AGILIDAD: SODA tiene carta libre para definir todos los detalles faltantes bajo su criterio profesional."

    current_prompt = user_prompt
    iteration = 0
    max_iterations = 5
    MAX_QUESTIONS_PER_BATCH = 5
    asked_questions: set = set()
    auto_decision_offered = False

    while iteration < max_iterations:
        iteration += 1
        if notify_fn:
            notify_fn(f"Analizando requerimientos (Iteración {iteration}/{max_iterations})...", "LOG")

        sys_p = (
            "Eres el Wisdom Agent de SODA. Tu misión es analizar el requerimiento del usuario y detectar ambigüedades críticas.\n"
            "Si el requerimiento es claro, devuelve is_clear_enough=True.\n"
            "Si falta información, devuelve is_clear_enough=False y genera preguntas directas.\n"
            "MANDATORIO: Responde siempre en formato JSON acorde al esquema proporcionado."
        )

        try:
            if rc3_agent:
                resp = await rc3_agent.execute_chunk(
                    task_desc=f"Analizar requerimientos y generar preguntas críticas para: {current_prompt}",
                    context="Fase de Sabiduría (Capa 0)",
                    target_files=[],
                    schema=WisdomEvaluation.model_json_schema()
                )
                eval_data = WisdomEvaluation(**resp)
            else:
                resp = await gemini_driver.call(
                    system_prompt=sys_p,
                    user_message=current_prompt,
                    response_schema=WisdomEvaluation.model_json_schema()
                )
                eval_data = WisdomEvaluation.model_validate_json(resp.content)

            if eval_data.is_clear_enough or iteration >= max_iterations:
                break

            new_questions = []
            for q_obj in eval_data.critical_questions:
                q_text = q_obj.question if isinstance(q_obj, WisdomQuestion) else q_obj
                if q_text not in asked_questions:
                    new_questions.append(q_text)
                    asked_questions.add(q_text)

            if not new_questions:
                break

            if notify_fn:
                notify_fn(f"El Consejo RC3 requiere {len(new_questions)} aclaraciones.", "LOG")

            for question in new_questions[:MAX_QUESTIONS_PER_BATCH]:
                answer = await ask_user_fn(question)
                if not answer or answer.lower() in ["si", "sí", "ok", "adelante", "procede", "avanza"]:
                    if not auto_decision_offered:
                        current_prompt += "\n\nINSTRUCCIÓN DE AGILIDAD: SODA tiene carta libre."
                        auto_decision_offered = True
                        return current_prompt
                    continue
                current_prompt += f"\n\nDETALLE SOBRE '{question}':\n{answer}"

        except Exception as e:
            if notify_fn:
                notify_fn(f"Wisdom RC3 falló ({e}). Usando modo lineal de emergencia.", "WARNING")
            break

    return current_prompt
