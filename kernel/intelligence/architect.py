"""Architect — generates and refines MasterContracts (Arquitecto v2).

Uses Gemini with a phased context-building approach.
"""
from __future__ import annotations

import json
from pathlib import Path

from kernel.drivers.gemini_driver import GeminiDriver
from kernel.intelligence.complexity_classifier import (
    MODEL_ASSIGNMENT_BY_COMPLEXITY,
    MODEL_CALL_CONFIG,
    ComplexityLevel,
)
from kernel.intelligence.contract_schemas import MasterContract

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts" / "gemini"


class Architect:
    """Generates and refines MasterContracts using Gemini.

    Phased Generation Process:
    1. Interpret & Divide tasks based on topology & blueprint.
    2. Establish Nexus (Communication Links).
    3. Define Sub-contracts (Data types, methods per module).
    4. Assemble Master Contract JSON.
    """

    def __init__(self, gemini_driver: GeminiDriver, builder=None, notify_fn=None):
        self.driver = gemini_driver
        self.builder = builder
        self.notify_fn = notify_fn

    async def generate_master_contract(
        self,
        blueprint: dict,
        complexity: ComplexityLevel,
        topology: dict | None = None,
        active_skills: list | None = None,
        active_profile: dict | None = None,
        goal_tree: dict | None = None,
        attempt_number: int = 1,
    ) -> MasterContract:
        """Generate the initial MasterContract in phases."""
        target_model = MODEL_ASSIGNMENT_BY_COMPLEXITY[complexity.value]

        # Helper to call Gemini and parse JSON
        async def ask_gemini(system_msg: str, user_msg: str, label: str) -> dict:
            if self.notify_fn:
                self.notify_fn(f"Architect Phase: {label}...", "LOG", {"phase": label})

            resp = await self.driver.call(
                system_prompt=system_msg,
                user_message=user_msg,
                response_format="json",
                **MODEL_CALL_CONFIG.get(target_model, {"max_tokens": 8192}),
                metadata={"phase": "master_contract", "step": label}
            )

            if resp.error_code:
                raise RuntimeError(f"Architect {label} failed [{resp.error_code}]: {resp.content}")
            return self._parse_json(resp.content)

        blueprint_str = json.dumps(blueprint, ensure_ascii=False)
        topology_str = json.dumps(topology or {}, ensure_ascii=False)

        # -------------------------------------------------------------
        # PHASE 1: Interpret and Divide (Responsabilities)
        # -------------------------------------------------------------
        p1_sys = "You are a software architect. Read the blueprint and topology. Output a JSON dict mapping each module ID to its specific responsibilities and tasks."
        p1_user = f"""BLUEPRINT:
{blueprint_str}

TOPOLOGY:
{topology_str}"""
        division_result = await ask_gemini(p1_sys, p1_user, "Phase 1 - Division")

        # -------------------------------------------------------------
        # PHASE 2: Establish Nexus (Links)
        # -------------------------------------------------------------
        p2_sys = "You are a software architect. Based on the modules and responsibilities, establish the interaction nexus between them. Output a JSON list of objects: {caller, callee, purpose}."
        p2_user = f"""MODULES:
{json.dumps(division_result)}

Define the strict communication links."""
        nexus_result = await ask_gemini(p2_sys, p2_user, "Phase 2 - Nexus")

        # -------------------------------------------------------------
        # PHASE 3: Sub-contracts (Data Types & Interfaces)
        # -------------------------------------------------------------
        p3_sys = "You are a software architect. Define the specific data types and method interfaces for each module based on the communication nexus. Output a JSON object containing 'data_types' and 'module_interfaces'."
        p3_user = f"""NEXUS:
{json.dumps(nexus_result)}

MODULES:
{json.dumps(division_result)}

Generate strict typed interfaces."""
        subcontracts_result = await ask_gemini(p3_sys, p3_user, "Phase 3 - Sub-contracts")

        # -------------------------------------------------------------
        # PHASE 4: Master Contract Assembly
        # -------------------------------------------------------------
        p4_sys = """You are a senior software architect assembling the final Master Contract JSON schema for SODA.
Output valid JSON matching the MasterContract schema: {
  "data_types": [...],
  "error_types": [...],
  "modulos": [ { "id", "name", "description", "layer", "dependencies", "interfaces": [ {name, params, return_type, is_async, description} ] } ]
}"""
        p4_user = f"""ASSEMBLE THIS INTO FINAL CONTRACT:

DIVISIONS: {json.dumps(division_result)}
NEXUS: {json.dumps(nexus_result)}
INTERFACES: {json.dumps(subcontracts_result)}"""
        
        contract_data = await ask_gemini(p4_sys, p4_user, "Phase 4 - Assembly")
        
        self._dump_raw(contract_data, label=f"generate_attempt{attempt_number}_{complexity.value}")
        contract_data = self._normalize_contract_data(contract_data)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = target_model

        try:
            contract = MasterContract(**contract_data)
        except Exception as exc:
            from pydantic import ValidationError
            if isinstance(exc, ValidationError):
                fields = "\n".join(
                    f"  {'.'.join(str(l) for l in e['loc'])}: {e['msg']}"
                    for e in exc.errors()[:12]
                )
                raise RuntimeError(f"MasterContract schema validation failed:\n{fields}") from exc
            raise

        if topology:
            contract = self._apply_topology_autofix(contract, topology)
        return contract

    async def refine_contract(
        self,
        current_contract: MasterContract,
        audit_feedback: object,
        complexity: ComplexityLevel,
        attempt_number: int = 2,
    ) -> MasterContract:
        """Refine a contract based on auditor feedback."""
        model = MODEL_ASSIGNMENT_BY_COMPLEXITY[complexity.value]
        system_prompt = "You are a software architect refining a JSON contract based on audit feedback. Output only the updated valid JSON MasterContract."
        feedback_text = audit_feedback.to_architect_feedback()
        user_message = f"""CURRENT CONTRACT:\n{current_contract.model_dump_json(indent=2)}\n\nFEEDBACK:\n{feedback_text}\n\nFix the issues and return the updated JSON."""

        response = await self.driver.call(
            system_prompt=system_prompt,
            user_message=user_message,

            response_format="json",
            **MODEL_CALL_CONFIG.get(model, {"max_tokens": 8192}),
        )

        if response.error_code:
            raise RuntimeError(f"Refinement failed: {response.content}")

        contract_data = self._parse_json(response.content)
        self._dump_raw(contract_data, label=f"refine_attempt{attempt_number}_{complexity.value}")
        contract_data = self._normalize_contract_data(contract_data)
        contract_data["complexity_level"] = complexity.value
        contract_data["model_used"] = model

        try:
            contract = MasterContract(**contract_data)
        except Exception as exc:
            raise RuntimeError(f"MasterContract schema validation failed on refinement: {exc}") from exc

        return contract

    @staticmethod
    def _parse_json(content: str) -> dict:
        import re
        content = content.strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"): lines = lines[1:]
            if lines[-1].startswith("```"): lines = lines[:-1]
            content = "\n".join(lines).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass
            return {"raw": content}

    @classmethod
    def _normalize_contract_data(cls, data: dict) -> dict:
        if "modulos" not in data:
            data["modulos"] = []
        for mod in data["modulos"]:
            if "interfaces" not in mod: mod["interfaces"] = []
            if "dependencies" not in mod: mod["dependencies"] = []
            if "layer" not in mod: mod["layer"] = "core"
            if "events_emitted" not in mod: mod["events_emitted"] = []
            if "events_consumed" not in mod: mod["events_consumed"] = []
            for iface in mod["interfaces"]:
                if "params" not in iface: iface["params"] = []
                if "is_async" not in iface: iface["is_async"] = False
                for p in iface["params"]:
                    if "required" not in p: p["required"] = True
        if "data_types" not in data: data["data_types"] = []
        if "error_types" not in data: data["error_types"] = []
        return data

    def _apply_topology_autofix(self, contract: MasterContract, topology: dict) -> MasterContract:
        return contract

    def _dump_raw(self, data: dict, label: str) -> None:
        pass


def generate_skeleton_contract(blueprint: dict, topology: dict) -> MasterContract:
    return MasterContract(modulos=[], data_types=[], error_types=[])

