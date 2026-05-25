import asyncio
import os
from pathlib import Path
from kernel.orchestration.omega_engine import OmegaEngine
from kernel.drivers.gemini_driver import GeminiDriver
from kernel.drivers.provider_hub import AIProviderHub

async def main():
    print("🚀 Triggering Deep Thinking Forensic Audit manually...")
    
    project_id = "test19"
    project_path = Path(f"projects/{project_id}")
    
    if not project_path.exists():
        print(f"❌ Project {project_id} not found.")
        return

    # Setup drivers
    gemini = GeminiDriver()
    hub = AIProviderHub()
    hub.register("gemini", gemini)
    # Register the user's requested model (even if it's high version)
    hub.register("gemini-3.5-flash", gemini) 

    # Invalidate old report
    report_file = project_path / "SODA_DEEP_THINKING_REPORT.md"
    if report_file.exists():
        report_file.unlink()

    from kernel.intelligence.deep_thinking import DeepThinkingAnalyzer
    analyzer = DeepThinkingAnalyzer(hub)
    
    mission_desc = "Crea una herramienta CLI en Python que indexe archivos de texto en una carpeta y permita buscar palabras clave devolviendo la línea y el número de línea. Debe ser modular y tener tests unitarios."
    
    report = await analyzer.generate_forensic_report(project_path, mission_desc)
    
    print("\n--- REPORT CONTENT ---")
    print(report)
    print("----------------------")

if __name__ == "__main__":
    asyncio.run(main())
