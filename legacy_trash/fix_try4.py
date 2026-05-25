import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# I see the problem. There's a `try:` at the end. We just need to remove it and its block entirely, 
# since I completely replaced `resume` earlier but didn't remove the bottom half of the old resume 
# that was at the end of the file.

pattern = re.compile(r'    async def resume_legacy.*?if __name__ == "__main__":', re.DOTALL)
# Actually, the old method was called `_phase_resume` or just part of `resume`. Let's just remove the dangling `try:` block.

pattern = re.compile(r'        try:\n            # Determine which phases are already complete.*?await self\._phase_wisdom\(project\)\n\n\nif __name__', re.DOTALL)
content = pattern.sub('if __name__', content)

# It seems `pattern.sub` didn't match. Let's do a more robust search
idx = content.rfind('        try:\n            # Determine which phases are already complete')
if idx != -1:
    end_idx = content.find('if __name__ == "__main__":', idx)
    if end_idx != -1:
        content = content[:idx] + content[end_idx:]

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
