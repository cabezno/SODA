from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict

class ContractStatus(str, Enum):
    PENDING_DECOMPOSITION = "PENDING_DECOMPOSITION"
    DECOMPOSED = "DECOMPOSED"
    PENDING_EXECUTION = "PENDING_EXECUTION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

ALLOWED_SKILLS = {
    "skill_fastapi", "skill_sqlite", "skill_langchain", "skill_anthropic", "skill_openai",
    "skill_typescript", "skill_react", "skill_angular", "skill_vue", "skill_nextjs", 
    "skill_nestjs", "skill_nodejs", "skill_golang", "skill_java_spring", 
    "skill_android_kotlin", "skill_flutter", "skill_csharp_dotnet", 
    "skill_cpp_cmake", "skill_php_laravel", "skill_rust", "skill_html", "skill_css"
}
BANNED_WORDS = {"obj", "data", "array", "item", "val", "info", "temp", "x", "y"}

class ContractVariable(BaseModel):
    name: str
    abstract_type: str
    desc: str

    @field_validator('name')
    def validate_clarity(cls, v):
        if len(v) <= 2: raise ValueError(f"Nombre '{v}' muy corto.")
        if any(banned == v.lower() for banned in BANNED_WORDS): raise ValueError(f"Término prohibido: '{v}'.")
        return v

class ContractInterface(BaseModel):
    inputs_required: List[ContractVariable] =[]
    outputs_provided: List[ContractVariable] =[]

class DynamicPersona(BaseModel):
    target_role: str
    required_skills: List[str]

    @field_validator('required_skills', mode='before')
    def validate_skills(cls, v):
        if not isinstance(v, list):
            return v
        processed = []
        for skill in v:
            skill_str = str(skill).lower().strip()
            # Prevent catastrophic pipeline failures by ensuring dynamic skills start with "skill_"
            if not skill_str.startswith("skill_"):
                skill_str = f"skill_{skill_str}"
            processed.append(skill_str)
        return processed
class SodaContract(BaseModel):
    contract_id: str
    parent_id: Optional[str] = None
    level: int = 0
    title: str
    description: str
    is_atomic: bool = False
    dependencies: List[str] =[]
    dynamic_persona: DynamicPersona
    interface: ContractInterface
    inherited_constraints: List[str] =[]
    status: ContractStatus = Field(default=ContractStatus.PENDING_DECOMPOSITION)

    @field_validator('status', mode='before')
    @classmethod
    def validate_status_robust(cls, v):
        if not v:
            return ContractStatus.PENDING_DECOMPOSITION
        if isinstance(v, ContractStatus):
            return v
        v_str = str(v).upper().strip()
        # Mapeo de sinónimos comunes que la IA inventa
        mapping = {
            "PENDING_IMPLEMENTATION": ContractStatus.PENDING_EXECUTION,
            "IN_PROGRESS": ContractStatus.PENDING_EXECUTION,
            "TODO": ContractStatus.PENDING_EXECUTION,
            "DONE": ContractStatus.COMPLETED,
            "SUCCESS": ContractStatus.COMPLETED,
            "REJECTED": ContractStatus.PENDING_DECOMPOSITION,
            "WAITING": ContractStatus.PENDING_DECOMPOSITION
        }
        if v_str in mapping:
            return mapping[v_str]
        
        # Si está en el enum, lo devolvemos tal cual
        try:
            return ContractStatus(v_str)
        except ValueError:
            # Si es algo desconocido, inferimos por convención
            return ContractStatus.PENDING_DECOMPOSITION

    @field_validator('dynamic_persona', mode='before')
    @classmethod
    def validate_persona_robust(cls, v):
        if isinstance(v, dict):
            # Mapeo de sinónimos comunes
            if 'role' in v and 'target_role' not in v:
                v['target_role'] = v['role']
            if 'skills' in v and 'required_skills' not in v:
                v['required_skills'] = v['skills']
            if 'target_role' not in v:
                v['target_role'] = "Developer" # Fallback
            if 'required_skills' not in v:
                v['required_skills'] = [] # Fallback
        return v

    @field_validator('interface', mode='before')
    @classmethod
    def validate_interface_robust(cls, v):
        if not v:
            return ContractInterface(inputs_required=[], outputs_provided=[])
        return v
