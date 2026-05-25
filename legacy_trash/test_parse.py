import json
from kernel.core.models_v2 import SodaContract, ContractInterface, DynamicPersona, ContractVariable

# Test if Pydantic requires any special handling for re-parsing
contract = SodaContract(
    contract_id="TEST-001",
    level=1,
    title="Test",
    description="Test",
    is_atomic=True,
    dynamic_persona=DynamicPersona(target_role="Dev", required_skills=["skill_fastapi"]),
    interface=ContractInterface(
        inputs_required=[ContractVariable(name="param_a", abstract_type="String", desc="desc")]
    )
)

js = contract.model_dump_json()
print("DUMP:", js)

try:
    c2 = SodaContract(**json.loads(js))
    print("RE-PARSE OK")
except Exception as e:
    print("RE-PARSE ERROR:", e)
