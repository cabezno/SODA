import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

patch_msg = """        if hasattr(self, "_notify"):
            self._notify("Esta funcionalidad está temporalmente deshabilitada por la migración a SODA V2.", "ERROR", {})
        import inspect
        # Return project or None depending on what it returns
        return getattr(self, "_active_project", None)"""

def disable_func(func_name, content):
    p = re.compile(rf'    async def {func_name}\(.*?\).*?:\n\s*""".*?"""', re.DOTALL)
    def repl(m):
        return m.group(0) + f"\n{patch_msg}\n"
    return p.sub(repl, content)

content = disable_func("import_from_code", content)
content = disable_func("open_and_process", content)
content = disable_func("_run_non_software_pipeline", content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
