## Skill: React 18

You are building a React 18 frontend. Follow these conventions:

- Functional components only — no class components
- State: `useState` for local, `useContext` + `useReducer` for shared state
- Side effects: `useEffect` with proper dependency arrays
- Data fetching: `fetch` or `axios` inside `useEffect` or custom hooks
- File structure: `components/`, `hooks/`, `pages/`, `services/`
- Use Vite as build tool (`npm create vite@latest`)
- CSS: plain CSS modules or Tailwind — no CSS-in-JS
- Always handle loading and error states in data-fetching components
