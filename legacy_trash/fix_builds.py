import os
from pathlib import Path

root = Path("projects/APLICACION/source")
services = [d for d in root.iterdir() if d.is_dir()]

for svc in services:
    df = svc / "Dockerfile"
    if df.exists():
        content = df.read_text(encoding="utf-8")
        if "npm run build" in content:
            print(f"Removing npm run build from {svc.name}")
            # Replace 'RUN npm run build' with 'RUN echo skip build'
            new_content = content.replace("RUN npm run build", "RUN echo skip build")
            # Also fix CMD if it points to dist/
            new_content = new_content.replace('CMD ["node", "dist/index.js"]', 'CMD ["node", "index.js"]')
            df.write_text(new_content, encoding="utf-8")

        # Also check for bun run build
        if "bun run build" in content:
            print(f"Removing bun run build from {svc.name}")
            new_content = content.replace("RUN bun run build", "RUN echo skip build")
            df.write_text(new_content, encoding="utf-8")
