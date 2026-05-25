import asyncio
import os
from kernel.orchestrator import SodaOrchestrator

async def main():
    # Descripción del proyecto con rigor de "Sistema Operativo"
    description = (
        "Dashboard de Gestión de Inventario Pro (SODA OMEGA PILOT). "
        "REQUERIMIENTOS DE NIVEL KERNEL:\n"
        "1. SEGURIDAD: Sistema de Autenticación JWT robusto con Refresh Tokens.\n"
        "2. PERSISTENCIA: Backend FastAPI con SQLite (SQLAlchemy) y soporte para migraciones.\n"
        "3. INTERFAZ: Frontend moderno (HTML/Tailwind o React) con Dashboard de analíticas.\n"
        "4. ROBUSTEZ: Manejo de excepciones global, logs de telemetría en cada función y validación de esquemas.\n"
        "5. AUDITORÍA: El sistema debe pasar los controles de DeepSeek y Claude para asegurar integridad total."
    )
    
    orch = SodaOrchestrator()
    
    # Lanzar el pipeline OMEGA (Aditivo: Gemini -> DeepSeek -> Claude)
    project = await orch.run_omega_project(
        description=description,
        project_name="OMEGA-INVENTORY-DASHBOARD"
    )
    
    print(f"\n[SODA OMEGA] Proyecto finalizado. Estado: {project.state}")
    print(f"[SODA OMEGA] Workspace: {project.workspace}")

if __name__ == "__main__":
    asyncio.run(main())
