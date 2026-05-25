from kernel.validators.v2.polyglot_validator import PolyglotValidator

text = """
<FILE path="test.py">
```python
print("hello")
```
</FILE>
<FILE path="test2.py">
```python
print("world"
"""

files = PolyglotValidator.extract_files(text)
for k, v in files.items():
    print(f"[{k}]: {v}")
