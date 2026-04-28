import sys
import re

file_path = 'kernel/orchestrator.py'
content = open(file_path, 'r', encoding='utf-8').read()

pattern = r'    async def _dev_qwen_copilot_loop\([\s\S]*?async def _intensity_review_module\('
new_content = re.sub(pattern, '    async def _intensity_review_module(', content)

if content != new_content:
    open(file_path, 'w', encoding='utf-8').write(new_content)
    print('Refactor successful: Removed _dev_qwen_copilot_loop and _intensity_copilot_loop')
else:
    print('Pattern not found')
