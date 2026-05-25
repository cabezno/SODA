import asyncio
import os
from kernel.orchestrator import SodaOrchestrator

async def main():
    description = (
        "Sistema de Intercambio de Criptoactivos con Seguridad de Nivel Bancario, "
        "auditoría de contratos inteligentes y Dashboard en tiempo real."
    )
    
    orch = SodaOrchestrator()
    project = await orch.run_omega_project(
        description=description,
        project_name="OMEGA-CRYPTO-EXCHANGE"
    )
    
    print(f"\n[SODA OMEGA] Proyecto finalizado. Estado: {project.state}")

if __name__ == "__main__":
    asyncio.run(main())
