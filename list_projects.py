from pathlib import Path
from kernel.projects.project_manager import ProjectManager

pm = ProjectManager(Path("."))
projects = pm.list_all()
for p in projects:
    print(f"ID: {p['id']}, State: {p['state']}, Created: {p['created_at']}")
