from pathlib import Path
path = Path('kernel/docker_sandbox.py')
content = path.read_text(encoding='utf-8')

old_line = "    def _ensure_connected(self) -> bool:"
new_block = """    @property
    def available(self) -> bool:
        \"\"\"Alias para compatibilidad con el resto de SODA.\"\"\"
        try:
            return self._ensure_connected()
        except:
            return False

    def _ensure_connected(self) -> bool:"""

if old_line in content:
    content = content.replace(old_line, new_block)
    path.write_text(content, encoding='utf-8')
    print("SUCCESS: .available restored.")
else:
    print("ERROR: Line not found.")
