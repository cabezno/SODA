import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List

class TemplateManager:
    """
    Gestiona la clonación y preparación de esqueletos (Boilerplates) Open Source.
    """
    # Catálogo de plantillas curadas
    TEMPLATES = {
        "python_fastapi": "https://github.com/tiangolo/full-stack-fastapi-template.git", # Ejemplo real
        "node_express": "https://github.com/sahat/hackathon-starter.git",
        "react_tailwind": "https://github.com/tailwindlabs/tailwindcss-setup-examples.git",
        "nextjs_app": "https://github.com/vercel/next.js.git"
    }

    def __init__(self, templates_dir: Path):
        self.base_dir = templates_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_template_path(self, template_key: str) -> Optional[Path]:
        """Clona una plantilla si no existe y devuelve su ruta."""
        url = self.TEMPLATES.get(template_key)
        if not url:
            return None
        
        target_path = self.base_dir / template_key
        if not target_path.exists():
            print(f"Clonando plantilla {template_key} desde {url}...")
            try:
                subprocess.run(["git", "clone", "--depth", "1", url, str(target_path)], check=True)
                # Limpiar .git para que no interfiera con el repo del proyecto
                shutil.rmtree(target_path / ".git", ignore_errors=True)
            except Exception as e:
                print(f"Error clonando plantilla: {e}")
                return None
        return target_path

    def scaffold_project(self, project_workspace: Path, template_key: str):
        """Copia el esqueleto al workspace del proyecto."""
        template_path = self.get_template_path(template_key)
        if not template_path:
            return False
        
        source_dir = project_workspace / "source"
        source_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Instalando esqueleto {template_key} en {source_dir}...")
        try:
            # Copiar contenido de la plantilla al source
            for item in os.listdir(template_path):
                s = template_path / item
                d = source_dir / item
                if s.is_dir():
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            return True
        except Exception as e:
            print(f"Error en scaffolding: {e}")
            return False
