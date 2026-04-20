import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE ENTORNO ---
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

# Carga explícita del .env desde la raíz
env_path = root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    print(f"[!] Advertencia: No se encontró el archivo .env en {env_path}")

import asyncio
from kernel.drivers.ollama_driver import OllamaDriver
from kernel.drivers.claude_driver import ClaudeDriver
from kernel.context.context_builder import ContextBuilder
from kernel.integrity.goal_integrity_validator import GoalIntegrityValidator

# ... (resto de la clase SodaOrchestrator y sus métodos)
from kernel.drivers.gemini_driver import GeminiDriver # Importar el nuevo driver

# ... (tus imports previos)

class SodaOrchestrator:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.builder = ContextBuilder()
        self.validator = GoalIntegrityValidator()
        
        # Inicialización de Drivers
        self.ollama = OllamaDriver()
        self.gemini = GeminiDriver()

    async def start_new_project(self, user_idea: str):
        print(f"[*] SODA: Iniciando fase de Requerimientos con Gemini...")
        
        payload = self.builder.build_payload(
            provider="gemini", 
            role="requirements_interviewer", 
            task_content=user_idea
        )
        
        # Ejecución síncrona en hilo aparte para no bloquear asyncio
        response = await asyncio.to_thread(self.gemini.prompt, payload['system'], payload['user'])
        
        print("\n--- RESPUESTA DEL ENTREVISTADOR (Gemini) ---")
        if "Error" in response:
            print(f"[!] Fallo en la comunicación: {response}")
        else:
            print(response)
        print("--------------------------------------------\n")
        return response

if __name__ == "__main__":
    orchestrator = SodaOrchestrator()
    
    # COMENTA la línea de execute_task (Desarrollo)
    # asyncio.run(orchestrator.execute_task(...))
    
    # DESCOMENTA la línea de start_new_project (Requerimientos)
    asyncio.run(orchestrator.start_new_project(
        "Quiero crear un sistema de gestión de turnos y automatización de entrega de archivos para mi estudio grabarpodcast.com"
    ))