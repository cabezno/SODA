# Build Infrastructure Checklist — React + Vite

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar dependencias ni correr scripts |
| `vite.config.ts` | Sin esto Vite no sabe cómo bundlear el proyecto |
| `tsconfig.json` | TypeScript no compila sin él |
| `tsconfig.node.json` | Configuración separada para el entorno Node.js (vite.config.ts) |
| `index.html` | Entry point del HTML; Vite lo usa como template de SPA |
| `src/main.tsx` | Entry point de React: `ReactDOM.createRoot(...).render(<App />)` |
| `src/App.tsx` | Componente raíz de la aplicación |
| `.env.example` | Variables de entorno para el frontend (prefijo `VITE_`) |
| `.env.local` | Variables reales en local; Vite las carga automáticamente |
| `.gitignore` | Debe excluir `node_modules/`, `dist/`, `.env.local`, `.env.*.local` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el dev server |
| `.vscode/launch.json` | Sin esto F5 no abre Chrome con sourcemaps |
| `.vscode/extensions.json` | Recomienda ES7 React snippets, ESLint, Prettier |

## Contenido mínimo de package.json

```json
{
  "name": "my-react-app",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.1",
    "@types/react-dom": "^18.3.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "eslint": "^8.57.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.6",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "vitest": "^1.6.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.0"
  }
}
```

## Contenido mínimo de vite.config.ts

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

## Contenido de tsconfig.json

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

## Contenido de tsconfig.app.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["src"]
}
```

## Contenido de tsconfig.node.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "noEmit": true
  },
  "include": ["vite.config.ts"]
}
```

## Contenido de index.html

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>My App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

## Contenido mínimo de .env.example

```
VITE_API_URL=http://localhost:8000
VITE_APP_TITLE=MyApp
VITE_APP_ENV=development
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "npm install",
      "type": "shell",
      "command": "npm install",
      "group": "build"
    },
    {
      "label": "Vite: Dev server",
      "type": "shell",
      "command": "npm run dev",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Vite: Build",
      "type": "shell",
      "command": "npm run build",
      "group": "build",
      "problemMatcher": ["$tsc"]
    },
    {
      "label": "Run tests",
      "type": "shell",
      "command": "npm test",
      "group": { "kind": "test", "isDefault": true }
    }
  ]
}
```

## .vscode/launch.json

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Chrome: Launch dev",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/src",
      "sourceMapPathOverrides": {
        "webpack:///src/*": "${webRoot}/*"
      },
      "preLaunchTask": "Vite: Dev server"
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "dsznajder.es7-react-js-snippets",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next",
    "bradlc.vscode-tailwindcss"
  ]
}
```

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar deps | `npm install` |
| Dev server | `npm run dev` |
| Build producción | `npm run build` |
| Preview del build | `npm run preview` |
| Tests | `npm test` |
| Linting | `npm run lint` |

## Reglas del auditor (checklist para código generado)

1. **Solo variables `VITE_*` son accesibles en el cliente** — todas las variables de entorno expuestas al browser deben tener el prefijo `VITE_`; sin el prefijo son undefined en tiempo de ejecución
2. **`"type": "module"` en package.json** — requerido para que Vite funcione con ESM nativo
3. **`src/main.tsx` usa `createRoot`** — API de React 18; nunca `ReactDOM.render()` (deprecado y removido)
4. **Componentes en archivos `.tsx`, hooks en `.ts`** — mantener la extensión correcta; `.ts` para lógica pura, `.tsx` para JSX
5. **`@vitejs/plugin-react` en vite.config.ts** — sin el plugin, JSX no se transforma y el HMR no funciona
6. **proxy de API en `vite.config.ts` para evitar CORS en dev** — requests a `/api` deben ser proxeadas al backend en desarrollo
7. **`tsconfig.app.json` separado de `tsconfig.node.json`** — Vite requiere esta separación desde v5; un solo tsconfig causa errores de tipo

## Errores comunes de generación AI

- Usar variables de entorno sin prefijo `VITE_` — el build no las expone al cliente
- No incluir `index.html` en la raíz (o ponerlo en `public/`) — Vite busca el HTML en la raíz del proyecto
- Usar `ReactDOM.render()` de React 17 — removido en React 18
- Generar un `tsconfig.json` monolítico en lugar del patrón `tsconfig.json` + `tsconfig.app.json` + `tsconfig.node.json` requerido por Vite 5
- `vite.config.ts` sin el import de `path` cuando se usa `alias` — causa error en runtime de Vite
- No configurar proxy en `vite.config.ts` — el frontend recibe errores CORS al llamar al backend en desarrollo
- Imports de assets con rutas relativas frágiles en lugar de alias `@/` — se rompen al reorganizar carpetas
- No incluir `@types/react` y `@types/react-dom` en devDependencies — TypeScript no reconoce JSX
