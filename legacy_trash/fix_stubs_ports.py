import os
from pathlib import Path

root = Path("projects/APLICACION/source")
services = [d for d in root.iterdir() if d.is_dir()]

# Node stub that actually listens on a port
NODE_STUB = """
const http = require('http');
const port = process.env.PORT || {PORT};
const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Stub service running on port ' + port);
});
server.listen(port, '0.0.0.0', () => {
  console.log('Server running on port ' + port);
});
"""

# Python stub that actually listens on a port
PYTHON_STUB = """
import os
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "service": "{SERVICE}"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", {PORT}))
    uvicorn.run(app, host="0.0.0.0", port=port)
"""

# Read docker-compose to map services to ports
dc_path = root / "docker-compose.yml"
import re
dc_content = dc_path.read_text(encoding="utf-8") if dc_path.exists() else ""

for svc in services:
    # Find port in docker-compose
    port_match = re.search(svc.name + r':.*?ports:.*?"(\d+):', dc_content, re.DOTALL)
    port = port_match.group(1) if port_match else "8080"
    
    df = svc / "Dockerfile"
    if df.exists():
        content = df.read_text(encoding="utf-8")
        
        if "node" in content.lower():
            idx_js = svc / "index.js"
            print(f"Updating Node stub for {svc.name} on port {port}")
            idx_js.write_text(NODE_STUB.replace("{PORT}", port), encoding="utf-8")
            
        if "python" in content.lower():
            main_py = svc / "main.py"
            print(f"Updating Python stub for {svc.name} on port {port}")
            main_py.write_text(PYTHON_STUB.replace("{PORT}", port).replace("{SERVICE}", svc.name), encoding="utf-8")
            
            # Update CMD to run main.py if it was something else
            if 'CMD ["fastapi"' in content:
                 new_content = content.replace('CMD ["fastapi", "run", "--workers", "4", "app/main.py"]', 'CMD ["python", "main.py"]')
                 df.write_text(new_content, encoding="utf-8")
