from typing import Any, Dict, List
from kernel.execution_engine.blueprint import ProjectBlueprint, Task

def translate_to_blueprint(project_name: str, soda_blueprint: Dict[str, Any]) -> ProjectBlueprint:
    """
    Traduce el blueprint de SODA-PROJECT (formato modulos) al formato Task-Graph de SODAA.
    """
    bp = ProjectBlueprint(project_name)
    
    # SODA-PROJECT suele devolver una lista de módulos en data['modulos'] o similar
    modulos = soda_blueprint.get("modulos", [])
    
    for mod in modulos:
        mod_id = mod.get("id", "unknown")
        descripcion = mod.get("descripcion", "")
        # Las interfaces se usan para fortalecer el contrato
        interfaces = mod.get("interfaces", [])
        contract_str = f"Interfaces requeridas:\n"
        for iface in interfaces:
            contract_str += f"- {iface.get('name')}({iface.get('params')}): {iface.get('description')}\n"
        
        # SODA-PROJECT usa 'dependencias' como nombres de otros módulos
        deps = mod.get("dependencias", [])
        if not isinstance(deps, list):
            deps = []
            
        task = Task(
            id=mod_id,
            description=descripcion,
            language=mod.get("lenguaje", "python"), # Fallback a python
            target_files=mod.get("archivos", []), # CAPTURAR RUTAS ORIGINALES
            dependencies=deps,
            contract=contract_str
        )
        bp.add_task(task)
        
    return bp
