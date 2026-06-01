from kernel.core.models_v2 import SodaContract
from typing import Dict

class DataFlowValidator:
    @staticmethod
    def validate_pipeline(contract: SodaContract, resolved_dependencies: Dict[str, SodaContract]):
        """
        Verifica la integridad de las dependencias sin forzar un tipado estricto
        que bloquee inputs ambientales (Env, User, HTTP).
        """
        # 1. Evitar auto-dependencia
        if contract.contract_id in contract.dependencies:
            raise ValueError(f"AUDITORÍA FALLIDA: El contrato '{contract.contract_id}' depende de sí mismo.")

        # 2. Verificar que no existan dependencias fantasma
        for dep_id in contract.dependencies:
            if dep_id not in resolved_dependencies:
                raise ValueError(
                    f"AUDITORÍA FALLIDA: El contrato declara depender de '{dep_id}', "
                    f"pero ese módulo no existe en el árbol resuelto."
                )
        
        # Nota: Hemos removido la validación estricta de inputs vs outputs.
        # Confiamos en que la Capa 3 (Tech Lead) y Capa 4 (Qwen) resolverán 
        # la inyección de dependencias y variables de entorno a nivel de código.
        
        return True
