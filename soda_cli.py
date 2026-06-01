import asyncio
import sys
import os
import json
from pathlib import Path
from colorama import init, Fore, Style
from datetime import datetime

# Añadir el path raíz para importaciones
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kernel.orchestrator import SodaOrchestrator, ProjectState, Project

init(autoreset=True)

class SodaInteractiveCLI:
    def __init__(self):
        self.orch = SodaOrchestrator()
        self.current_session_id = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._user_response_event = asyncio.Event()
        self._last_user_response = ""

    async def ask_user_bridge(self, question: str) -> str:
        """Permite que el kernel de SODA haga preguntas al usuario en medio del build."""
        print("\n" + Fore.YELLOW + "❓ PREGUNTA DE SODA:")
        print(Fore.WHITE + Style.BRIGHT + question)
        
        # En una consola síncrona dentro de un loop async, usamos loop.run_in_executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: input(Fore.GREEN + "Tu respuesta > " + Style.RESET_ALL).strip())
        return response

    async def run(self):
        print(Fore.CYAN + Style.BRIGHT + "========================================")
        print(Fore.CYAN + Style.BRIGHT + "       SODA FUSION — MODO INTERACTIVO   ")
        print(Fore.CYAN + Style.BRIGHT + "========================================")
        print(Fore.WHITE + "Estás hablando con el Liaison Agent (X-HIGH).")
        print(Fore.YELLOW + "Comandos: /build (construir), /status, /exit")
        print("")

        workspace = self.orch.projects_dir / self.current_session_id
        workspace.mkdir(parents=True, exist_ok=True)
        
        active_project = Project(
            id=self.current_session_id, 
            description="Sesión de Chat Interactiva", 
            workspace=workspace,
            state=ProjectState.IDLE
        )
        self.orch._active_project = active_project
        self.orch._save_state(active_project)

        print(Fore.MAGENTA + "SODA > " + Style.RESET_ALL + "¡Hola! Soy SODA. ¿Qué vamos a construir hoy?")

        while True:
            try:
                user_input = input(Fore.GREEN + "Tú > " + Style.RESET_ALL).strip()
                
                if not user_input: continue
                if user_input.lower() == "/exit": break
                
                if user_input.lower() == "/status":
                    print(Fore.BLUE + f"Sesión: {self.current_session_id} | Estado: {self.orch._active_project.state.value}")
                    continue

                if user_input.lower() == "/build":
                    print(Fore.MAGENTA + "\n[X-HIGH] Consolidando requerimientos...")
                    hardened_desc = await self.orch.liaison_agent.extract_hardened_description()
                    
                    print(Fore.CYAN + "--- ESPECIFICACIÓN TÉCNICA ---")
                    print(Fore.WHITE + hardened_desc[:300] + "...")
                    
                    print(Fore.GREEN + "\n🚀 Iniciando Pipeline OMEGA (Soportando preguntas interactiva)...")
                    try:
                        # MAGIA: Pasamos el bridge de preguntas al kernel
                        await self.orch.run_omega_project(
                            hardened_desc, 
                            self.current_session_id, 
                            ask_user_fn=self.ask_user_bridge
                        )
                        print(Fore.GREEN + "\n✅ PROYECTO COMPLETADO.")
                    except Exception as e:
                        print(Fore.RED + f"\n[!] Error en el build: {e}")
                    continue

                # CHAT NORMAL
                response = await self.orch.liaison_agent.chat(user_input, {
                    "blueprint": active_project.blueprint,
                    "architecture": active_project.architecture
                })
                print(Fore.MAGENTA + "\nSODA > " + Style.RESET_ALL + response + "\n")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(Fore.RED + f"\n[!] Error: {e}")

if __name__ == "__main__":
    cli = SodaInteractiveCLI()
    asyncio.run(cli.run())
