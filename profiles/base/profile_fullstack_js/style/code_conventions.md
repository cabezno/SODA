# Fullstack JS Code Conventions

- TypeScript everywhere — both frontend and backend share type definitions in `shared/types/`
- Backend: Express with async/await, centralized error handler, input validation
- Frontend: React or Vue with hooks/composables for data fetching
- Single `package.json` at root with workspaces, or separate `/client` and `/server` folders
- Environment variables: `.env` files, never committed; `.env.example` always committed
- REST API responses follow `{ data, error, message }` envelope pattern
