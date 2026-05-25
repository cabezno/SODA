import re

with open("kernel/drivers/gemini_driver.py", "r", encoding="utf-8") as f:
    content = f.read()

# Add model to the call signature
content = re.sub(
    r'(response_schema:\s*dict\s*\|\s*None\s*=\s*None,)',
    r'\1\n        model: str | None = None,',
    content
)

# Replace the usage of self.active_model inside the method with the override
content = re.sub(
    r'model_used=self\.active_model or self\.candidate_models\[0\]',
    r'model_used=model or self.active_model or self.candidate_models[0]',
    content
)

content = re.sub(
    r'_resolve_gemini_max_tokens\(self\.active_model,\s*max_tokens\)',
    r'_resolve_gemini_max_tokens(model or self.active_model, max_tokens)',
    content
)

content = re.sub(
    r'if "2\.5-flash" in \(self\.active_model or ""\):',
    r'if "2.5-flash" in (model or self.active_model or ""):',
    content
)

content = re.sub(
    r'url = f"https://generativelanguage\.googleapis\.com/v1beta/models/\{self\.active_model or self\.candidate_models\[0\]\}:generateContent\?key=\{self\.api_key\}"',
    r'url = f"https://generativelanguage.googleapis.com/v1beta/models/{{model or self.active_model or self.candidate_models[0]}}:generateContent?key={{self.api_key}}"',
    content
)

with open("kernel/drivers/gemini_driver.py", "w", encoding="utf-8") as f:
    f.write(content)
