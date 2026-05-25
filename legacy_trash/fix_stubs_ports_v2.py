import os
from pathlib import Path
import re

root = Path("projects/APLICACION/source")
services = [d for d in root.iterdir() if d.is_dir()]

dc_path = root / "docker-compose.yml"
dc_content = dc_path.read_text(encoding="utf-8") if dc_path.exists() else ""

# Fixed ports based on docker-compose.yml analysis
# ceo-research-003: 3009
# ceo-finance-004: 3008
# ui-001-services: 3002
# ui-001-console: 3000
# ui-001-dashboard: 3001
# ui-001-tasks: 3004
# ui-001-shell: 3003
# ceo-core-002-persistence: 3007
# ceo-core-002-brain: 3005
# ceo-core-002-gateway: 3006

PORTS = {
    "ceo-research-003": "3009",
    "ceo-finance-004": "3008",
    "ui-001-services": "3002",
    "ui-001-console": "3000",
    "ui-001-dashboard": "3001",
    "ui-001-tasks": "3004",
    "ui-001-shell": "3003",
    "ceo-core-002-persistence": "3007",
    "ceo-core-002-brain": "3005",
    "ceo-core-002-gateway": "3006",
    "backend": "8000"
}

NODE_STUB = """
const http = require('http');
const port = {PORT};
const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Stub service running on port ' + port);
});
server.listen(port, '0.0.0.0', () => {
  console.log('Server running on port ' + port);
});
"""

PYTHON_STUB = """
import os
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "service": "{SERVICE}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port={PORT})
"""

for svc_name, port in PORTS.items():
    svc = root / svc_name
    if not svc.exists(): continue
    
    df = svc / "Dockerfile"
    if df.exists():
        content = df.read_text(encoding="utf-8")
        if "node" in content.lower():
            (svc / "index.js").write_text(NODE_STUB.replace("{PORT}", port), encoding="utf-8")
        if "python" in content.lower():
            (svc / "main.py").write_text(PYTHON_STUB.replace("{PORT}", port).replace("{SERVICE}", svc_name), encoding="utf-8")
            
            # Ensure Dockerfile uses python main.py
            if "CMD" in content and "python" not in content:
                new_content = re.sub(r'CMD \[.*\]', 'CMD ["python", "main.py"]', content)
                df.write_text(new_content, encoding="utf-8")
