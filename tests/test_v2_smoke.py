import asyncio
import unittest
from pathlib import Path
from kernel.orchestrator import SodaOrchestrator
from kernel.core.models_v2 import SodaContract

class TestSodaV2Smoke(unittest.IsolatedAsyncioTestCase):
    async def test_orchestrator_init(self):
        """Verifica que el orquestador se inicialice con todos sus nuevos componentes."""
        orch = SodaOrchestrator()
        self.assertIsNotNone(orch.blackbox, "BlackBox Logger no inicializado")
        self.assertIsNotNone(orch.gemini, "Gemini Driver no inicializado")
        self.assertIsNotNone(orch.ai_hub.blackbox, "BlackBox no vinculado al AI Hub")

    async def test_finops_router(self):
        """Verifica que el router de FinOps devuelva alineaciones válidas."""
        from kernel.intelligence.finops_router import FinopsRouter
        lineup = FinopsRouter.get_lineup("balanced")
        self.assertEqual(lineup.layer0_wisdom, "gemini-3-flash-preview")
        self.assertEqual(lineup.layer5_qa, "gemini-3-flash-preview")

    async def test_contract_schema(self):
        """Verifica la integridad del esquema Pydantic de SodaContract."""
        data = {
            "contract_id": "TEST-001",
            "level": 1,
            "title": "Test Contract",
            "description": "Just a test",
            "is_atomic": True,
            "dynamic_persona": {
                "target_role": "Tester",
                "required_skills": ["python"]
            },
            "interface": {
                "inputs_required": [],
                "outputs_provided": []
            }
        }
        contract = SodaContract(**data)
        self.assertEqual(contract.contract_id, "TEST-001")
        self.assertEqual(contract.dynamic_persona.target_role, "Tester")

if __name__ == "__main__":
    unittest.main()
