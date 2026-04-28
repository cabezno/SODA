# Frontend Dev Code Conventions

- Components are single-responsibility, small, and composable
- No inline styles — use CSS modules, Tailwind, or styled-components consistently
- All user-facing text in the language of the project description
- Loading states and error states are always handled visibly
- Props are typed; no implicit any
- Folder: `components/` for reusable UI, `pages/` or `views/` for routes
- API calls are isolated in `services/` or `api/` — never inline in components
