from dataclasses import dataclass, field
from typing import Dict

@dataclass
class ModuleRetryState:
    module_id: str
    attempts: int = 0
    max_retries: int = 3
    fatigue_level: float = 0.0  # 0.0 to 1.0
    errors: list[str] = field(default_factory=list)

    def increment(self, error: str):
        self.attempts += 1
        self.errors.append(error)
        self.fatigue_level = min(1.0, self.attempts / self.max_retries)

    @property
    def exhausted(self) -> bool:
        return self.attempts >= self.max_retries

@dataclass
class RetryContext:
    project_id: str
    module_states: Dict[str, ModuleRetryState] = field(default_factory=dict)

    def get_state(self, module_id: str, max_retries: int = 3) -> ModuleRetryState:
        if module_id not in self.module_states:
            self.module_states[module_id] = ModuleRetryState(module_id=module_id, max_retries=max_retries)
        return self.module_states[module_id]

    def reset(self, module_id: str):
        if module_id in self.module_states:
            del self.module_states[module_id]
