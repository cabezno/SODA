from typing import Any, Dict, List, Optional


def detect_language_from_tree(v2_tree: Dict[str, Any]) -> Optional[str]:
    """
    Deriva el lenguaje (o lenguajes) escanendo las skills de TODOS los contratos.
    Soporta detección polyglot.
    """
    all_skills: List[str] = []
    for contract_data in v2_tree.values():
        persona  = contract_data.get("dynamic_persona") or {}
        required = persona.get("required_skills") or []
        all_skills.extend(str(s) for s in required)
    if not all_skills:
        return None
    return detect_polyglot_language(all_skills)


def detect_polyglot_language(skills: List[str]) -> str:
    """Detects primary language or combined string for polyglot projects."""
    langs = detect_all_languages(skills)
    if not langs: return "python"
    if len(langs) == 1: return langs[0]
    return " + ".join(langs)


def detect_all_languages(skills: List[str]) -> List[str]:
    """Detects all programming languages present in a list of skills."""
    skills_str = " ".join([s.lower() for s in skills if isinstance(s, str)])
    found = []
    
    if any(x in skills_str for x in ["typescript", "nextjs", "react", "angular", "nestjs", "skill_vue", "skill_svelte"]):
        found.append("typescript")
    if "nodejs" in skills_str and "typescript" not in found:
        found.append("javascript")
    if "python" in skills_str or "fastapi" in skills_str or "flask" in skills_str:
        if "python" not in found: found.append("python")
    if "golang" in skills_str or "skill_go" in skills_str:
        found.append("go")
    if "rust" in skills_str:
        found.append("rust")
    if "java_spring" in skills_str or "skill_java" in skills_str:
        found.append("java")
    if "android_kotlin" in skills_str or "skill_kotlin" in skills_str:
        found.append("kotlin")
    if "flutter" in skills_str:
        found.append("dart")
    
    # If nothing found but skills exist, default to python
    if not found and skills:
        found.append("python")
        
    return found


def detect_language(skills: List[str]) -> str:
    """Detects the primary programming language from a list of skills."""
    if not skills:
        return "python"
    
    skills_str = " ".join([s.lower() for s in skills if isinstance(s, str)])

    if any(x in skills_str for x in ["typescript", "nextjs", "react", "angular", "nestjs", "skill_vue", "skill_svelte"]):
        return "typescript"
    if "nodejs" in skills_str:
        return "javascript"
    if "python" in skills_str or "fastapi" in skills_str or "flask" in skills_str:
        return "python"
    if "golang" in skills_str or "skill_go" in skills_str:
        return "go"
    if "rust" in skills_str:
        return "rust"
    if "java_spring" in skills_str or "skill_java" in skills_str:
        return "java"
    if "android_kotlin" in skills_str or "skill_kotlin" in skills_str:
        return "kotlin"
    if "flutter" in skills_str:
        return "dart"
    if "skill_html" in skills_str or "skill_css" in skills_str:
        return "html"
    if "cpp" in skills_str or "skill_cpp_cmake" in skills_str:
        return "cpp"
    if "csharp" in skills_str or "skill_csharp_dotnet" in skills_str:
        return "csharp"

    # Default stack
    return "python"

def language_to_extension(language: str) -> str:
    """Maps a language name to its standard file extension."""
    lang = language.lower().strip()
    ext_map = {
        "python": ".py",
        "typescript": ".ts",
        "javascript": ".js",
        "go": ".go",
        "rust": ".rs",
        "java": ".java",
        "kotlin": ".kt",
        "dart": ".dart",
        "html": ".html",
        "css": ".css",
        "cpp": ".cpp",
        "cmake": ".txt",
        "csharp": ".cs",
        "json": ".json",
        "markdown": ".md",
        "yaml": ".yaml",
        "sql": ".sql",
    }
    return ext_map.get(lang, ".txt")

