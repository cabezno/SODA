import re
import glob

files_to_patch = [
    "kernel/capabilities/skill_matcher.py",
    "kernel/capabilities/profile_matcher.py",
    "kernel/capabilities/profile_evolution.py",
    "kernel/intelligence/wisdom_agent.py",
    "kernel/intelligence/goal_interpreter.py",
    "kernel/intelligence/impact_analyzer.py",
    "kernel/intelligence/refoundation.py",
    "kernel/intelligence/copilot_consultant.py",
    "kernel/intelligence/conformance_verifier.py",
    "kernel/testing/test_generator.py",
    "kernel/testing/functional_test_generator.py",
    "kernel/security/security_reviewer.py",
    "kernel/execution/boot_agent.py",
]

for filepath in files_to_patch:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Common cleanup pattern: remove claude_driver references from __init__
        content = re.sub(r",\s*claude_driver(?:=[^,\)]+)?", "", content)
        content = re.sub(r"\s*self\.claude\s*=\s*claude_driver\n", "\n", content)
        
        # Replace remaining self.claude calls with self.gemini
        content = content.replace("self.claude.", "self.gemini.")
        content = content.replace("claude_driver: ClaudeDriver", "gemini_driver: GeminiDriver")
        
        # Replace literal strings if they pass it inside
        content = content.replace('"claude"', '"gemini"')
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")
    except Exception as e:
        print(f"Failed to patch {filepath}: {e}")
