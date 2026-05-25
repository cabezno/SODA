import asyncio
import unittest
from unittest.mock import MagicMock, AsyncMock
from kernel.intelligence.recursive_council import RecursiveCouncilAgent
from kernel.core.project_index import MasterIndex, IndexSection

class TestRC3Core(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mock del AI Hub y los drivers
        self.ai_hub = MagicMock()
        
        self.mock_gemini = AsyncMock()
        self.mock_claude = AsyncMock()
        self.mock_deepseek = AsyncMock()
        
        self.ai_hub.get.side_effect = lambda name: {
            "gemini": self.mock_gemini,
            "claude": self.mock_claude,
            "deepseek": self.mock_deepseek
        }.get(name)

        self.agent = RecursiveCouncilAgent(self.ai_hub)

    async def test_rc3_sequential_integration(self):
        """Verifica que el flujo Gemini -> Claude -> DeepSeek -> Gemini (Merge) sea respetado."""
        
        # 1. Gemini entrega borrador inicial con un error (ej. falta un import)
        self.mock_gemini.call.side_effect = [
            AsyncMock(content="<FILE path='app.py'>def hello(): print('hi')</FILE>"), # Draft
            AsyncMock(content="<FILE path='app.py'>import sys\ndef hello(): print('hi')</FILE>") # Final Merge
        ]
        
        # 2. Claude detecta el error y manda extension
        self.mock_claude.call.return_value = AsyncMock(content="<EXTENSION_A>Falta importar sys</EXTENSION_A>")
        
        # 3. DeepSeek agrega otra extension
        self.mock_deepseek.call.return_value = AsyncMock(content="<EXTENSION_B>Código limpio</EXTENSION_B>")

        result = await self.agent.execute_chunk(
            task_desc="Crea un script simple",
            context="Contexto de prueba",
            target_files=["app.py"]
        )

        # Verificaciones
        self.assertIn("app.py", result)
        self.assertIn("import sys", result["app.py"]) # El merge final debió incluir la sugerencia
        self.assertEqual(self.mock_gemini.call.call_count, 2)
        self.assertEqual(self.mock_claude.call.call_count, 1)
        self.assertEqual(self.mock_deepseek.call.call_count, 1)

    def test_master_index_chunking(self):
        """Verifica que el modelo de datos de indexación maneje correctamente la estructura."""
        section = IndexSection(
            id="S1", title="Sec 1", description="Desc",
            sub_indices=[
                IndexSection(id="S1.1", title="Sub 1.1", description="D1", target_files=["f1.py"]),
                IndexSection(id="S1.2", title="Sub 1.2", description="D2", target_files=["f2.py"])
            ]
        )
        
        master = MasterIndex(
            project_id="P1", title="Test", total_sections=1,
            sections=[section]
        )
        
        flat = master.get_flat_sections()
        self.assertEqual(len(flat), 2)
        self.assertEqual(flat[0].id, "S1.1")
        self.assertEqual(flat[1].id, "S1.2")

if __name__ == "__main__":
    unittest.main()
