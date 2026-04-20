import re

class GoalIntegrityValidator:
    def __init__(self):
        self.metadata_pattern = re.compile(
            r'--- METADATA SODA ---\s*# goal_id: (.*?)\s*# goal_hash: (.*?)\s*--- FIN METADATA ---', 
            re.DOTALL
        )

    def validate_content(self, content: str) -> bool:
        match = self.metadata_pattern.search(content)
        if match:
            print(f'[✓] Integridad: Goal ID detectado.')
            return True
        print('[!] Error de Integridad: Metadata SODA no encontrada.')
        return False

    def extract_metadata(self, content: str):
        match = self.metadata_pattern.search(content)
        if match:
            return {'goal_id': match.group(1), 'goal_hash': match.group(2)}
        return None
