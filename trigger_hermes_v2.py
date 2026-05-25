import asyncio
import os
from kernel.orchestrator import SodaOrchestrator

async def main():
    print("🚀 Iniciando Proyecto: HERMES-REBORN-V2")
    print("Target: Clon de Hermes con Memoria Reutilizable y Aprendizaje de Hitos.")
    
    desc = (
        "Crea un agente tipo Hermes (Task Orchestrator) con las siguientes mejoras:\n"
        "1. Memoria de Largo Plazo: Usa SQLite para guardar contextos de proyectos pasados.\n"
        "2. Análisis de Hitos: Tras completar una meta, el agente debe extraer qué pasos fueron exitosos.\n"
        "3. Reruteo de Contexto: Capacidad de usar aprendizajes previos en nuevas metas.\n"
        "4. Interfaz: Una API en FastAPI y una consola clara.\n"
        "REGLA: Mantén la arquitectura simple (máximo 3 archivos core)."
    )
    
    orch = SodaOrchestrator()
    # Forzamos modo no-interactivo para la prueba automatizada
    project = await orch.run(desc, project_name="HERMES-REBORN-V2")
    
    print(f"\n✅ Pipeline Finalizado. Estado: {project.state.value}")
    if project.state.value == "done":
        print("🎉 SODA ha logrado generar y arrancar la aplicación con éxito.")
    else:
        print(f"❌ Fallo detectado. Revisa los logs en projects/{project.id}/logs/")

if __name__ == "__main__":
    asyncio.run(main())
