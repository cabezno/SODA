import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace driver import
content = re.sub(r"from kernel\.drivers\.claude_driver import ClaudeDriver\n", "", content)

# Remove self.claude.clear_history()
content = re.sub(r"\s*if hasattr\(self, \"claude\"\) and hasattr\(self\.claude, \"clear_history\"\):\s*self\.claude\.clear_history\(\)", "", content)

# Replace _call_claude with _call_gemini_pro
content = content.replace("def _call_claude(", "def _call_gemini_pro(")
content = content.replace("self._call_claude", "self._call_gemini_pro")
content = content.replace('"claude": ("Claude", self._call_gemini_pro),', '"gemini_pro": ("Gemini Pro", self._call_gemini_pro),')
content = content.replace('chain = [("Claude", self._call_gemini_pro), ("Gemini", self._call_gemini)]', 'chain = [("Gemini Pro", self._call_gemini_pro), ("Gemini", self._call_gemini)]')

# Update hardcoded strings
content = content.replace("Claude Sonnet", "Gemini Pro")
content = content.replace("Claude capacity error", "Gemini Pro capacity error")
content = content.replace("Claude evaluates ALL", "Gemini evaluates ALL")
content = content.replace("[Claude/eval]", "[Gemini/eval]")
content = content.replace("Claude supervisor", "Gemini supervisor")
content = content.replace("Claude/Gemini corrige", "Gemini corrige")
content = content.replace("Claude review/arbiter", "Gemini review/arbiter")
content = content.replace("Claude AND Gemini, then Claude arbiter", "Gemini Pro AND Gemini Flash, then Gemini arbiter")
content = content.replace("IMPLEMENTATION A (Claude)", "IMPLEMENTATION A (Gemini Pro)")
content = content.replace('"claude",', '"gemini_pro",')
content = content.replace('"claude": ["claude", "gemini", "openai", "ollama"],', '"gemini_pro": ["gemini", "openai", "ollama"],')

# Change self.claude to self.gemini inside _call_gemini_pro
content = re.sub(r"await self\._dispatch_call\(self\.claude, \"claude\", \"Claude\", role, task, project\)", r"await self._dispatch_call(self.gemini, \"gemini\", \"Gemini Pro\", role, task, project)", content)

# Clean up any leftover self.claude references
content = content.replace("self.claude.", "self.gemini.")
content = content.replace("self.claude", "self.gemini")

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
