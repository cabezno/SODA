import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from kernel.orchestration.omega_engine import OmegaEngine

@pytest.mark.asyncio
async def test_self_healing_conformance_trigger():
    """
    Verifica que el ciclo de autoreparación se active cuando
    un módulo no cumple con su contrato simbólico.
    """
    # 1. Mock de drivers e infraestructura
    mock_gemini = AsyncMock()
    mock_hub = MagicMock()
    mock_notify = MagicMock()
    
    # Simular un workspace temporal
    from pathlib import Path
    import tempfile
    tmp_ws = Path(tempfile.mkdtemp())
    src_dir = tmp_ws / "source"
    src_dir.mkdir()
    
    # Escribir un archivo con error de contrato (falta una función requerida)
    # El contrato pide 'login' y 'get_token', pero solo escribimos 'login'
    (src_dir / "auth.py").write_text("def login(u, p): return True", encoding="utf-8")
    
    engine = OmegaEngine(
        gemini_driver=mock_gemini,
        ai_hub=mock_hub,
        notify_fn=mock_notify,
        workspace=tmp_ws
    )
    
    # 2. Simular un MasterContract que exige 'get_token'
    blueprint = {
        "modulos": [
            {
                "id": "auth",
                "nombre": "auth",
                "archivos": ["auth.py"],
                "interfaces": [
                    {"name": "login", "params": [{"name": "u"}, {"name": "p"}]},
                    {"name": "get_token", "params": [{"name": "uid"}]}
                ]
            }
        ]
    }

    # Mock del desarrollador para la reparación
    mock_dev = AsyncMock()
    mock_dev.call.return_value = MagicMock(content="<FILE path='auth.py'>\ndef login(u, p): return True\ndef get_token(uid): return 'token'\n</FILE>")
    engine.developer = mock_dev

    # 3. Ejecutar la verificación y reparación
    files = {"auth.py": (src_dir / "auth.py").read_text()}
    await engine._verify_and_repair_conformance(files, blueprint)

    # 4. Validar que se detectó el error y se llamó a la reparación
    # Debe haber un log de ERROR indicando que no cumple el contrato
    error_calls = [c for c in mock_notify.call_args_list if c[0][1] == "ERROR" and "no cumple el contrato" in c[0][0]]
    assert len(error_calls) > 0
    
    # Validar que el archivo en memoria ahora tiene la función faltante
    assert "def get_token" in files["auth.py"]
