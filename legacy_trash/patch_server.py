import re
with open("ui/server.py", "r", encoding="utf-8") as f:
    content = f.read()

# Remove the temporary V2 bypass injection
start_marker = "            # --- SODA V2 INJECTION ---"
end_marker = "            # -------------------------\n"
pattern = re.compile(re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL)
content = pattern.sub("", content)

with open("ui/server.py", "w", encoding="utf-8") as f:
    f.write(content)
