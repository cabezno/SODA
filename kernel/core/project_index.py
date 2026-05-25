from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class IndexSection(BaseModel):
    id: str
    title: str
    description: str
    estimated_tokens: int = 4000
    sub_indices: List['IndexSection'] = []
    status: str = "pending"
    target_files: List[str] = []
    relay_note: Optional[str] = Field(None, description="Technical decisions and context for the next agent.")

class MasterIndex(BaseModel):
    project_id: str
    title: str
    total_sections: int
    sections: List[IndexSection]
    output_length_limit: int = 8192
    
    def get_flat_sections(self) -> List[IndexSection]:
        flat = []
        def traverse(section):
            if not section.sub_indices:
                flat.append(section)
            else:
                for sub in section.sub_indices:
                    traverse(sub)
        for s in self.sections:
            traverse(s)
        return flat
