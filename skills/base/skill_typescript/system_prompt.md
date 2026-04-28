## Skill: TypeScript

You are writing TypeScript. Follow these conventions:

- Enable strict mode in `tsconfig.json`: `"strict": true`
- Never use `any` — use `unknown` when type is truly dynamic
- Define interfaces for all data contracts; use `type` aliases for unions/intersections
- Use generics to avoid duplication in collections and utilities
- Prefer `readonly` for properties that should not be mutated
- Use `enum` for named constants; use `const enum` for performance when values are static
- All async functions return `Promise<T>` — be explicit about return types
- `tsconfig.json` target: `"ES2020"` or later
