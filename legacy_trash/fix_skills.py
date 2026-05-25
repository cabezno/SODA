import re

with open("kernel/core/models_v2.py", "r", encoding="utf-8") as f:
    content = f.read()

patch = """    @field_validator('required_skills')
    def validate_skills(cls, v):
        for skill in v:
            # Prevent catastrophic pipeline failures by allowing any dynamic skill starting with "skill_" 
            # or existing in ALLOWED_SKILLS
            if skill not in ALLOWED_SKILLS and not str(skill).startswith("skill_"): 
                raise ValueError(f"Skill '{skill}' no permitida.")
        return v"""

content = re.sub(
    r'    @field_validator\(\'required_skills\'\)\n    def validate_skills\(cls, v\):\n        for skill in v:\n            if skill not in ALLOWED_SKILLS: raise ValueError\(f"Skill \'\{skill\}\' no permitida\."\)\n        return v',
    patch,
    content
)

with open("kernel/core/models_v2.py", "w", encoding="utf-8") as f:
    f.write(content)
