import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Quitar ClaudeDriver de imports y de __init__
content = re.sub(r'from kernel\.drivers\.claude_driver import ClaudeDriver\n', '', content)
content = re.sub(r'self\.claude = ClaudeDriver\(\)\n', '', content)

# 2. Reemplazar todas las inicializaciones que usaban `claude_driver=self.claude` o `claude_driver=self.gemini`
# por `gemini_driver=self.gemini`
content = content.replace("claude_driver=self.claude", "gemini_driver=self.gemini")
content = content.replace("self.claude", "self.gemini")

# 3. Solucionar el problema del doble `gemini_driver=self.gemini` que se crea
content = content.replace("gemini_driver=self.gemini, gemini_driver=self.gemini", "gemini_driver=self.gemini")
content = re.sub(r'gemini_driver=self\.gemini,\s*gemini_driver=self\.gemini', 'gemini_driver=self.gemini', content)

# 4. Solucionar CodeGenerator que recibe demasiados parámetros
content = content.replace("CodeGenerator(self.ollama, self.gemini, self.gemini)", "CodeGenerator(self.ollama, self.gemini)")

# 5. Arreglar Ollama active_model
content = content.replace('ollama_model=self.ollama.active_model', 'ollama_model=self.ollama.model')

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
