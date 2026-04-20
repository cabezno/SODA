import re

class GoalIntegrityValidator:
    def __init__(self):
        self.metadata_pattern = re.compile(
            r'#\s*---\s*METADATA SODA.*?---.*?'
            r'#\s*goal_id:\s*(?P<goal_id>.+?)\n'
            r'.*?'
            r'#\s*goal_hash:\s*(?P<goal_hash>.+?)\n'
            r'.*?'
            r'#\s*---\s*FIN METADATA\s*---',
            re.DOTALL,
        )

    def validate_content(self, content: str) -> bool:
        match = self.metadata_pattern.search(content)
        if match:
            print('[OK] Integridad: Goal ID detectado.')
            return True
        print('[!] Error de Integridad: Metadata SODA no encontrada.')
        return False

    def extract_metadata(self, content: str):
        match = self.metadata_pattern.search(content)
        if match:
            return {'goal_id': match.group('goal_id').strip(), 'goal_hash': match.group('goal_hash').strip()}
        return None
