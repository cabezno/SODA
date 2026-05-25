import pytest
import json
from pathlib import Path
from kernel.execution_engine.blueprint import ProjectBlueprint, Task
from kernel.execution_engine.adapter import translate_to_blueprint

def test_blueprint_translation_integrity():
    """
    Test que verifica que la traducción del blueprint de SODA-PROJECT 
    a SODAA mantiene la integridad de los contratos e interfaces.
    """
    # 1. Simular un blueprint de SODA-PROJECT con interfaces complejas
    soda_project_blueprint = {
        "modulos": [
            {
                "id": "auth_service",
                "descripcion": "Servicio de autenticación",
                "lenguaje": "python",
                "dependencias": [],
                "interfaces": [
                    {"name": "login", "params": "user, password", "description": "Valida credenciales"},
                    {"name": "get_token", "params": "user_id", "description": "Genera JWT"}
                ]
            },
            {
                "id": "user_api",
                "descripcion": "API de usuarios",
                "lenguaje": "python",
                "dependencias": ["auth_service"],
                "interfaces": [
                    {"name": "create_user", "params": "data", "description": "Crea un usuario"}
                ]
            }
        ]
    }

    # 2. Ejecutar traducción
    fusion_bp = translate_to_blueprint("TestProject", soda_project_blueprint)

    # 3. Validaciones
    assert isinstance(fusion_bp, ProjectBlueprint)
    assert len(fusion_bp.tasks) == 2
    
    # Verificar que auth_service tiene sus interfaces en el contrato
    auth_task = fusion_bp.tasks["auth_service"]
    assert "login(user, password)" in auth_task.contract
    assert "get_token(user_id)" in auth_task.contract
    
    # Verificar dependencias
    user_task = fusion_bp.tasks["user_api"]
    assert "auth_service" in user_task.dependencies

def test_contract_drift_prevention_logic():
    """
    Verifica que el CodeGenerator reciba la información de contrato correcta.
    Este test actúa como 'faro' para evitar regresiones donde el LLM 
    inventa sus propias interfaces.
    """
    from kernel.code_generator import CodeGenerator
    from unittest.mock import MagicMock

    # Mock de drivers
    mock_ollama = MagicMock()
    gen = CodeGenerator(mock_ollama)

    # Datos de prueba
    module = {
        "id": "database",
        "responsabilidad": "Gestionar persistencia",
        "interfaces": [{"name": "save", "parameters": {"data": "dict"}, "returns": "bool"}]
    }
    
    # Simular Master Contract v2
    master_contract = {
        "modules": [
            {
                "id": "database",
                "interfaces": [{"name": "save", "parameters": {"data": "dict"}, "returns": "bool"}]
            }
        ]
    }

    # Generar el prompt de la tarea
    task_json = gen._build_task(
        filepath="database.py",
        module=module,
        blueprint={},
        architecture={},
        master_contract=master_contract
    )
    
    task_data = json.loads(task_json)
    
    # VERIFICACIÓN CRÍTICA: ¿Se incluyó la interfaz tipada?
    assert "interfaz_a_implementar" in task_data
    assert task_data["interfaz_a_implementar"][0]["name"] == "save"
    assert "data" in task_data["interfaz_a_implementar"][0]["parameters"]
