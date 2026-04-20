from pathlib import Path
from typing import Optional, Dict

class ContextBuilder:
    def __init__(self):
        # Localiza la raíz del proyecto SODA (sube 3 niveles desde kernel/context/cb.py)
        self.base_dir = Path(__file__).parent.parent.parent
        self.prompts_dir = self.base_dir / 'prompts'

    def build_payload(self, provider: str, role: str, task_content: str, extra_context: Optional[str] = None) -> Dict[str, str]:
        """
        Busca el system prompt en /prompts/{provider}/{role}.md 
        y ensambla el mensaje para el driver.
        """
        prompt_path = self.prompts_dir / provider / f'{role}.md'
        
        if not prompt_path.exists():
            # Fallback por si el archivo no existe
            system_instruction = f"Eres un agente de SODA especializado en {role}."
        else:
            # Leemos con UTF-8 explícito para evitar errores de Windows
            system_instruction = prompt_path.read_text(encoding='utf-8')

        user_message = task_content
        if extra_context:
            user_message = f"CONTEXTO PREVIO:\n{extra_context}\n\nTAREA ACTUAL:\n{task_content}"

        return {
            'system': system_instruction,
            'user': user_message
        }
