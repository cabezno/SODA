## Skill: Angular

You are building an Angular 17+ application. Follow these conventions:

- Use standalone components (`standalone: true`) — avoid NgModules for new projects
- All components use `OnPush` change detection strategy by default
- Services use `providedIn: 'root'` — no need to declare in providers array
- Use Angular Signals (`signal()`, `computed()`, `effect()`) for reactive state in Angular 17+
- HTTP calls go through `HttpClient` injected via `inject()` in a service layer, never in components
- Use typed reactive forms (`FormGroup<...>`) not template-driven forms for complex forms
- All routes in `app.routes.ts` with lazy loading via `loadComponent`
- Environments in `src/environments/environment.ts` and `environment.prod.ts`
