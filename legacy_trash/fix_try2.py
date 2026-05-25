import re

with open("kernel/orchestrator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Try to find the orphaned except block by looking for the specific error strings.
# Since we replaced the `try` block that was associated with this, this `except` is now hanging.

pattern = re.compile(r'        except Exception as e:\s*import traceback as _tb\s*project\.state = ProjectState\.FAILED\s*self\._save_state\(project\)\s*self\._notify\(f"Error crÃ­tico en el pipeline.*?(?=        return project)', re.DOTALL)
content = pattern.sub('', content)

# I also noticed another set of except blocks:
content = re.sub(r'        except Exception as e:\n\n          # Phase 3: generate output bundle', r'        # Phase 3: generate output bundle', content)

with open("kernel/orchestrator.py", "w", encoding="utf-8") as f:
    f.write(content)
