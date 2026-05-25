import re

with open("kernel/orchestration/recursive_engine.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add max_depth check in decompose_tree
patch_loop = """            target_contract = contracts_pool[target_id]
            self._notify("LOG", f"Capa 2: Analizando y descomponiendo contrato maestro '{target_id}' (Level: {target_contract.level})...")
            
            # --- SECURITY FALLBACK: MAX DEPTH ---
            if target_contract.level >= 4:
                self._notify("WARNING", f"  ↳ Nivel máximo de recursión alcanzado (4). Forzando is_atomic=True para {target_id}.")
                target_contract.is_atomic = True
                target_contract.status = "PENDING_EXECUTION"
                continue
"""

content = re.sub(
    r'            target_contract = contracts_pool\[target_id\]\n            self\._notify\("LOG", f"Capa 2: Analizando y descomponiendo contrato maestro \'{target_id}\'\.\.\."\)\n',
    patch_loop,
    content
)

with open("kernel/orchestration/recursive_engine.py", "w", encoding="utf-8") as f:
    f.write(content)
