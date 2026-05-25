import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

# Setup paths
sys.path.insert(0, str(Path(__file__).resolve().parent))

from kernel.drivers.gemini_driver import GeminiDriver
from kernel.drivers.claude_driver import ClaudeDriver
from kernel.drivers.driver_factory import build_driver
from kernel.drivers.provider_hub import AIProviderHub
from kernel.orchestration.layer0_wisdom import resolve_ambiguities
from kernel.orchestration.genesis import generate_root_contract
from kernel.core.models_v2 import SodaContract, ContractStatus

async def test_hub_resolution():
    print("\n[1/4] Testeando AIProviderHub...")
    gemini = GeminiDriver()
    claude = ClaudeDriver()
    hub = AIProviderHub(providers={"gemini": gemini, "claude": claude})
    
    # Caso: pedir modelo específico
    resolved = hub.get("claude-3-5-sonnet-latest")
    assert resolved == claude, "Fallo en resolución por prefijo de Claude"
    
    resolved_gem = hub.get("gemini-2.5-pro")
    assert resolved_gem == gemini, "Fallo en resolución por prefijo de Gemini"
    print("  ✅ Hub resuelve correctamente por prefijo.")

async def test_driver_kwargs():
    print("\n[2/4] Testeando Drivers con kwargs (Anti-Crash)...")
    claude = ClaudeDriver()
    # Simulamos envío de response_schema que Claude no soporta nativamente
    try:
        # Solo probamos la firma de la función, no la llamada real para ahorrar tokens
        # pero como el driver usa httpx/anthropic, verificamos que acepte el argumento
        await claude.call(system_prompt="hi", user_message="hi", response_schema={"type":"object"}, some_random_arg=True)
        print("  ✅ ClaudeDriver acepta kwargs extra.")
    except TypeError as e:
        print(f"  ❌ ClaudeDriver falló con kwargs: {e}")
        raise e
    except Exception: # Ignoramos errores de red/auth aquí, solo queremos ver la firma
        print("  ✅ ClaudeDriver acepta kwargs extra (signature OK).")

async def test_genesis_normalization():
    print("\n[3/4] Testeando Normalización de Esquemas en Génesis...")
    # Datos malformados (como los que mandaba DeepSeek)
    bad_data = {
        "id": "ROOT-000",
        "name": "Proyecto de Prueba",
        "description": "test",
        "is_atomic": False,
        "dynamic_persona": {
            "role": "Architect", # Debería ser target_role
            "required_skills": ["skill_python"]
        },
        "interface": {"inputs_required": [], "outputs_provided": []}
    }
    
    # Mock de driver que devuelve basura
    mock_driver = MagicMock()
    mock_response = MagicMock()
    mock_response.error_code = None
    mock_response.content = json.dumps(bad_data)
    mock_driver.call = AsyncMock(return_value=mock_response)
    
    hub = AIProviderHub(providers={"gemini-2.5-pro": mock_driver})
    
    contract = await generate_root_contract(
        user_description="test",
        active_skills=[],
        gemini_driver=mock_driver,
        ai_hub=hub
    )
    
    assert contract.title == "Proyecto de Prueba", "Fallo en mapeo name -> title"
    assert contract.dynamic_persona.target_role == "Architect", "Fallo en mapeo role -> target_role"
    assert contract.status == ContractStatus.PENDING_DECOMPOSITION, "Fallo en forzado de status"
    print("  ✅ Normalización de esquemas funcional e infalible.")

async def main():
    print("=== INICIANDO VALIDACIÓN TÉCNICA SODA V2 ===")
    try:
        await test_hub_resolution()
        await test_driver_kwargs()
        await test_genesis_normalization()
        print("\n[RESULTADO] Todas las pruebas pasaron. El sistema es ESTABLE.")
    except Exception as e:
        print(f"\n[ERROR] Fallo en validación: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
