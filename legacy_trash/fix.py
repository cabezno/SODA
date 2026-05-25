import re
import io

with open('kernel/code_generator.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = re.compile(r'    def _build_task\(.*?\n    def _validate_syntax\(', re.DOTALL)

with open('patch.txt', 'r', encoding='utf-8') as f:
    new_content = f.read()

# Make sure newlines in the string literal are preserved
new_content = new_content.replace('\\n#', '\\\\n#')

new_text = pattern.sub(new_content, text)

with open('kernel/code_generator.py', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Parche aplicado con éxito.")
