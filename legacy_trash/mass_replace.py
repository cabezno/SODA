import os, glob

for root, _, files in os.walk("kernel"):
    for file in files:
        if not file.endswith(".py"): continue
        path = os.path.join(root, file)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "claude" in content.lower() or "Claude" in content:
            # We skip complexity_classifier as we already fixed it
            if "complexity_classifier" in path or "architect.py" in path:
                # wait, we already completely replaced architect.py
                pass
            
            # Simple replacements to ensure no driver errors
            content = content.replace("claude_driver", "gemini_driver")
            content = content.replace("self.claude.", "self.gemini.")
            content = content.replace("self.claude", "self.gemini")
            content = content.replace("ClaudeDriver", "GeminiDriver")
            content = content.replace("_call_claude_haiku", "_call_gemini_flash")
            content = content.replace("_call_claude", "_call_gemini_pro")
            content = content.replace('"claude"', '"gemini"')
            content = content.replace("'claude'", "'gemini'")
            content = content.replace("Claude", "Gemini")
            content = content.replace("claude-sonnet-4-6", "gemini-2.5-pro")
            content = content.replace("claude-haiku-4-5-20251001", "gemini-2.5-flash")
            content = content.replace("claude", "gemini")
            
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Cleaned {path}")
