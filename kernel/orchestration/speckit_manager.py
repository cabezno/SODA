import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

class SpecKitManager:
    """
    Manages Spec-Kit artifacts (SDD) within a project's directory.
    Ensures that AI agents have access to the Constitution, Spec, Plan, and Tasks.
    """

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.specify_path = project_path / ".specify"
        self.memory_path = self.specify_path / "memory"
        
        # Ensure directory structure
        self.specify_path.mkdir(parents=True, exist_ok=True)
        self.memory_path.mkdir(parents=True, exist_ok=True)

    def initialize_constitution(self, global_rules: List[str] = None):
        """Generates the project's constitution based on SODA global rules and project-specific needs."""
        constitution_file = self.specify_path / "constitution.md"
        
        if constitution_file.exists():
            return # Don't overwrite existing project laws

        rules = global_rules or [
            "1. ZERO-HOST POLICY: All execution MUST happen inside the Docker Sandbox.",
            "2. ATOMIC COMMITS: Changes must be tracked and validated before moving to the next task.",
            "3. NO PLACEHOLDERS: All code generated must be complete and functional.",
            "4. SPEC-DRIVEN: Any change must have a corresponding entry in tasks.md.",
            "5. POLYGLOT INTEGRITY: Ensure imports are consistent across files and languages."
        ]

        content = "# SODA PROJECT CONSTITUTION\n\n"
        content += "This document defines the immutable rules for this project. All AI agents must adhere to these standards.\n\n"
        content += "## Core Rules\n"
        for rule in rules:
            content += f"- {rule}\n"
        
        content += "\n## Project Intent\n"
        content += "This project was generated via SODA Multi-Agent Orchestration. Maintain architectural purity at all costs.\n"
        
        constitution_file.write_text(content, encoding="utf-8")

    def save_spec(self, requirements: str):
        """Persists the business requirements as a spec.md file."""
        spec_file = self.project_path / "spec.md"
        content = f"# PROJECT SPECIFICATION (Business Requirements)\n\n{requirements}\n"
        spec_file.write_text(content, encoding="utf-8")

    def save_plan(self, technical_plan: Dict[str, Any]):
        """Persists the technical architecture as a plan.md file."""
        plan_file = self.project_path / "plan.md"
        
        content = "# TECHNICAL ARCHITECTURE PLAN\n\n"
        content += f"## Title: {technical_plan.get('title', 'Project Plan')}\n\n"
        
        if "modulos" in technical_plan:
            content += "### Modules\n"
            for mod in technical_plan["modulos"]:
                content += f"#### {mod['id']}: {mod['descripcion']}\n"
                content += "- **Files:** " + ", ".join(mod.get("archivos", [])) + "\n"
                if "interfaces" in mod:
                    content += "- **Interfaces:**\n"
                    for iface in mod["interfaces"]:
                        content += f"  - `{iface['name']}({iface.get('params', '')})`: {iface.get('description', '')}\n"
        
        if "stack" in technical_plan:
            content += f"\n### Technology Stack\n{technical_plan['stack']}\n"
            
        plan_file.write_text(content, encoding="utf-8")

    def sync_tasks(self, master_index: Any):
        """Syncs the internal JSON MasterIndex with a human-readable tasks.md."""
        tasks_file = self.project_path / "tasks.md"
        
        content = "# EXECUTION TASKS TRACKER\n\n"
        content += "Status markers: [ ] Pending, [/] In Progress, [x] Completed, [!] Failed\n\n"
        
        sections = master_index.get_flat_sections() if hasattr(master_index, "get_flat_sections") else []
        
        for section in sections:
            status_map = {
                "pending": " ",
                "in_progress": "/",
                "completed": "x",
                "done": "x",
                "failed": "!"
            }
            marker = status_map.get(section.status.lower(), " ")
            content += f"- [{marker}] **{section.id}**: {section.title}\n"
            content += f"  - *Description:* {section.description}\n"
            if section.target_files:
                content += f"  - *Files:* {', '.join(section.target_files)}\n"
            if hasattr(section, "relay_note") and section.relay_note:
                content += f"  - *Relay Note:* {section.relay_note}\n"
            content += "\n"
            
        tasks_file.write_text(content, encoding="utf-8")

    def save_relay_note(self, section_id: str, note: str):
        """Persists a relay note for a specific section."""
        note_file = self.memory_path / f"relay_{section_id.replace('.', '_')}.md"
        content = f"# RELAY NOTE: {section_id}\n\n{note}\n"
        note_file.write_text(content, encoding="utf-8")

    def get_all_relay_notes(self) -> str:
        """Retrieves all historical relay notes to maintain context integrity."""
        notes = "--- HISTORIAL DE RELEVOS (Technical Memory) ---\n"
        files = sorted(list(self.memory_path.glob("relay_*.md")))
        
        if not files:
            return ""

        for f in files:
            notes += f"\n{f.read_text(encoding='utf-8')}\n"
        
        notes += "--------------------------------------------\n"
        return notes

    def get_context_for_agent(self) -> str:
        """Returns a combined string of the Spec-Kit artifacts to inject into an agent's context."""
        context = "--- SPEC-KIT CONTEXT ---\n"
        
        files = {
            "Constitution": self.specify_path / "constitution.md",
            "Specification": self.project_path / "spec.md",
            "Plan": self.project_path / "plan.md",
            "Tasks": self.project_path / "tasks.md"
        }
        
        for name, path in files.items():
            if path.exists():
                context += f"\n### {name}\n{path.read_text(encoding='utf-8')}\n"
        
        context += "------------------------"
        return context
