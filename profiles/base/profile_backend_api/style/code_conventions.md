# Backend API Code Conventions

- Snake_case everywhere in Python
- Separate schemas from models: `schemas/` holds Pydantic, `models/` holds SQLAlchemy
- Router files named after resource: `routers/users.py`, `routers/tasks.py`
- CRUD functions: `create_X`, `get_X`, `get_all_X`, `update_X`, `delete_X`
- Always return the updated/created object after mutations
- Error messages in English, descriptive: "User with email {email} already exists"
- Consistent prefix: all routes under `/api/v1/`
