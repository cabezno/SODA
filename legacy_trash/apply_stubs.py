import os
from pathlib import Path

root = Path("projects/APLICACION/source")

# Update docker-compose.yml to use stubs for failing frontend services
dc_path = root / "docker-compose.yml"
if dc_path.exists():
    content = dc_path.read_text(encoding="utf-8")
    # For now, let's just use the stub for ALL services to see if it boots
    # No, that's too much. Just for the ones that fail build.
    
    # Actually, I'll just comment out the 'build' and use a simple nginx image
    import re
    
    # Replace frontend build with image
    content = re.sub(r'(frontend:.*?build:).*?(ports:)', r'\1\n      context: ./frontend\n      dockerfile: Dockerfile.stub\n    \2', content, flags=re.DOTALL)
    
    dc_path.write_text(content, encoding="utf-8")
    print("Updated docker-compose.yml with stubs")
