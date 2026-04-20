# Web Full-Stack Code Conventions

## Backend (Python)
- Snake_case for variables, functions, modules
- PascalCase for classes and Pydantic schemas
- Schemas: `UserCreate`, `UserRead`, `UserUpdate` — never expose ORM models directly
- Group routes: `/api/v1/users`, `/api/v1/auth`, `/api/v1/[resource]`

## Frontend (React)
- PascalCase for components, camelCase for functions and variables
- One component per file, filename matches component name
- Custom hooks prefixed with `use`: `useAuth`, `useFetch`, `useTasks`
- API calls centralized in `services/api.js`

## General
- `.env` for secrets, `.env.example` committed to repo
- README with setup instructions and available endpoints
