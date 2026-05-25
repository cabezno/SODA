import re
from pathlib import Path

f = Path("kernel/orchestrator.py")
content = f.read_text(encoding="utf-8")

# 1. Importación
if "from kernel.utils.blackbox_logger import SodaLogger" not in content:
    content = content.replace(
        "from kernel.intelligence.conformance_verifier import ConformanceVerifier",
        "from kernel.intelligence.conformance_verifier import ConformanceVerifier\nfrom kernel.utils.blackbox_logger import SodaLogger"
    )

# 2. Inicialización en __init__
init_target = "self._load_custom_providers()"
init_replacement = "self._load_custom_providers()\n        self.blackbox = SodaLogger()"
if init_target in content and "self.blackbox" not in content:
    content = content.replace(init_target, init_replacement)

# 3. Actualización de blackbox cuando hay workspace (run)
run_target = "project.profile = self._get_global_profile()"
run_replacement = "project.profile = self._get_global_profile()\n        self.blackbox = SodaLogger(project.workspace)"
if run_target in content:
    content = content.replace(run_target, run_replacement)

# 4. Actualización de blackbox cuando hay workspace (resume)
resume_target = "project = self._project_from_disk(project_id)"
resume_replacement = "project = self._project_from_disk(project_id)\n        self.blackbox = SodaLogger(project.workspace)"
if resume_target in content:
    content = content.replace(resume_target, resume_replacement)

f.write_text(content, encoding="utf-8")
print("Orchestrator actualizado con BlackBox Logger.")
