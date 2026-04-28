## Skill: Vue 3

You are building a Vue 3 application. Follow these conventions:

- Use Composition API with `<script setup>` syntax — no Options API
- State management with Pinia: one store per domain, use `defineStore`
- Routing with Vue Router 4: define routes in `router/index.ts`
- Use `ref()` for primitives, `reactive()` for objects
- Components are PascalCase files in `components/`; views in `views/`
- Props defined with `defineProps<{...}>()`, emits with `defineEmits<{...}>()`
- `axios` or `fetch` for API calls, wrapped in composables (`useXxx`)
- `vite` as the build tool; `npm run dev` to start
