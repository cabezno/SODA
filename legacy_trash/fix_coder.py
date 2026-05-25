import re

with open("prompts/v2/layer4_coder.md", "r", encoding="utf-8") as f:
    content = f.read()

patch = """2. **FORMATO OBLIGATORIO:** DEBES encerrar absolutamente todo el código generado dentro de un único bloque markdown (ej. ```python ... ``` o ```typescript ... ```).
3. NO incluyas listas numeradas, explicaciones, prefijos de línea, ni números de línea antes o dentro del código."""

content = re.sub(
    r'2\. \*\*FORMATO OBLIGATORIO:\*\* DEBES encerrar absolutamente todo el código generado dentro de un bloque markdown \(ej\. ```python \.\.\. ``` o ```typescript \.\.\. ```\)\.', 
    patch, 
    content
)

with open("prompts/v2/layer4_coder.md", "w", encoding="utf-8") as f:
    f.write(content)
