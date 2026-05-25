import re

with open("kernel/drivers/ollama_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

patch = """import psutil
def _resolve_model_sync(host: str, preferred: list[str]) -> str:
    \"\"\"Return 14b if RAM is sufficient, else fallback to 7b.\"\"\"
    try:
        import ollama
        client = ollama.Client(host=host)
        available = {m["name"] for m in client.list().get("models", [])}
        
        # Hardware Check
        ram = psutil.virtual_memory()
        free_ram_gb = ram.available / (1024 ** 3)
        
        # 14b usually needs at least ~10GB of free RAM/VRAM combined to run decently
        # If we have less than 8GB of system RAM free, we aggressively fallback to 7b.
        if "qwen2.5-coder:14b" in available and free_ram_gb >= 8.0:
            return "qwen2.5-coder:14b"
        elif "qwen2.5-coder:7b" in available:
            if free_ram_gb < 8.0:
                print(f"  [Ollama] RAM crítica detectada ({free_ram_gb:.1f}GB libres). Activando fallback a Qwen 7B.")
            return "qwen2.5-coder:7b"
            
        # Standard fallback if neither specific logic hits
        for candidate in preferred:
            if candidate in available:
                return candidate
    except Exception:
        pass
    return preferred[-1]"""

content = re.sub(r'def _resolve_model_sync\(.*?return preferred\[-1\]', patch, content, flags=re.DOTALL)

with open("kernel/drivers/ollama_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
