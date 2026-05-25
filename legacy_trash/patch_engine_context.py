import re
from pathlib import Path

f = Path("kernel/orchestration/recursive_engine.py")
content = f.read_text(encoding="utf-8")

# 1. Asegurar que el motor tenga acceso al blackbox desde el orquestador
# El orquestador ya le pasa self.blackbox? No, el orquestador lo crea. 
# Vamos a modificar el orquestador para pasar el logger al motor.

# En recursive_engine.py, vamos a añadir el campo opcional blackbox al __init__
init_target = "self.save_file_fn = save_file_fn"
init_replacement = "self.save_file_fn = save_file_fn\n        self.blackbox = getattr(ai_hub, 'blackbox', None) if ai_hub else None"

if init_target in content and "self.blackbox" not in content:
    content = content.replace(init_target, init_replacement)

# 2. Inyectar set_context en el bucle de decompose_tree (Capa 2)
decomp_target = 'target_contract = contracts_pool[target_id]'
decomp_replacement = 'target_contract = contracts_pool[target_id]\n            if self.blackbox: self.blackbox.set_context(phase="Fase de Arquitectura", node=target_id)'

if decomp_target in content:
    content = content.replace(decomp_target, decomp_replacement)

# 3. Inyectar set_context en process_contract (Capa 4/5)
proc_target = 'contract = atomic_contracts[cid]'
proc_replacement = 'contract = atomic_contracts[cid]\n                if self.blackbox: self.blackbox.set_context(phase="Fase de Desarrollo", node=cid)'

if proc_target in content:
    content = content.replace(proc_target, proc_replacement)

f.write_text(content, encoding="utf-8")
print("RecursiveEngine: Correlación de nodos activada.")
