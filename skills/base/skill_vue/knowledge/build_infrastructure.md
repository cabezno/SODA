# Build Infrastructure Checklist — Vue 3 + Vite

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar Vue ni correr scripts |
| `vite.config.ts` | Sin esto Vite no sabe cómo bundlear el proyecto |
| `tsconfig.json` | TypeScript no compila sin él |
| `tsconfig.app.json` | Configuración TypeScript para el código de la app |
| `tsconfig.node.json` | Configuración TypeScript para vite.config.ts |
| `index.html` | Entry point del HTML; Vite lo usa como template de SPA |
| `src/main.ts` | Entry point de Vue: `createApp(App).mount('#app')` |
| `src/App.vue` | Componente raíz de la aplicación |
| `env.d.ts` | Declaración de tipos para variables de entorno Vite |
| `.env.example` | Variables de entorno (prefijo `VITE_`) |
| `.env.local` | Variables reales en local; Vite las carga automáticamente |
| `.gitignore` | Debe excluir `node_modules/`, `dist/`, `.env.local`, `.env.*.local` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el dev server |
| `.vscode/launch.json` | Sin esto F5 no abre Chrome con sourcemaps |
| `.vscode/extensions.json` | Recomienda Volar (Vue Official), TypeScript Vue Plugin |

## Contenido mínimo de package.json

```json
{
  "name": "my-vue-app",
  "version": "0.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext .vue,.ts,.tsx --ignore-path .gitignore",
    "test:unit": "vitest run"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "pinia": "^2.1.0",
    "vue-router": "^4.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "@vue/eslint-config-typescript": "^13.0.0",
    "@vue/test-utils": "^2.4.0",
    "@vue/tsconfig": "^0.5.0",
    "eslint": "^8.57.0",
    "eslint-plugin-vue": "^9.23.0",
    "npm-run-all2": "^6.2.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "vitest": "^1.6.0",
    "vue-tsc": "^2.0.0"
  }
}
```

## Contenido de vite.config.ts

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
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
    { "path": "./tsconfig.node.json" },
    { "path": "./tsconfig.app.json" }
  ]
}
```

## Contenido de tsconfig.app.json

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["env.d.ts", "src/**/*", "src/**/*.vue"],
  "exclude": ["src/**/__tests__/*"]
}
```

## Contenido de tsconfig.node.json

```json
{
  "extends": "@tsconfig/node20/tsconfig.json",
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "types": ["node"]
  },
  "include": ["vite.config.*"]
}
```

## Contenido de env.d.ts

```typescript
/// <reference types="vite/client" />
```

## Estructura de carpetas recomendada

```
my-vue-app/
├── src/
│   ├── assets/
│   ├── components/
│   │   └── MyComponent.vue
│   ├── composables/          ← hooks reutilizables
│   │   └── useMyFeature.ts
│   ├── router/
│   │   └── index.ts          ← Vue Router
│   ├── stores/               ← Pinia stores
│   │   └── myStore.ts
│   ├── views/                ← componentes de página
│   │   └── HomeView.vue
│   ├── App.vue
│   └── main.ts
├── index.html
├── env.d.ts
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── package.json
├── .env.example
└── .gitignore
```

## Contenido de src/main.ts (con Pinia + Router)

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
```

## Contenido mínimo de .env.example

```
VITE_APP_TITLE=MyApp
VITE_API_URL=http://localhost:8000
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
      "group": "build"
    },
    {
      "label": "Run tests",
      "type": "shell",
      "command": "npm run test:unit",
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
      "preLaunchTask": "Vite: Dev server"
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "Vue.volar",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
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
| Tests | `npm run test:unit` |
| Linting | `npm run lint` |

## Reglas del auditor (checklist para código generado)

1. **Solo variables `VITE_*` accesibles en el cliente** — todas las variables de entorno expuestas al browser deben tener el prefijo `VITE_`
2. **Composition API con `<script setup>`** — usar `<script setup lang="ts">` en todos los componentes nuevos; evitar Options API en proyectos nuevos
3. **`vue-tsc` para type-checking de templates** — usar `vue-tsc -b` en el script de build, no solo `tsc`; los tipos de templates `.vue` requieren el compilador de Vue
4. **`env.d.ts` con `/// <reference types="vite/client" />`** — sin esto TypeScript no reconoce `import.meta.env`
5. **Extension Volar (Vue Official) recomendada** — Vetur es incompatible con Vue 3 Composition API; debe usarse Volar
6. **Props y emits tipados** — usar `defineProps<{ propName: type }>()` y `defineEmits<{ eventName: [arg: type] }>()`
7. **Pinia stores con `defineStore`** — si se usa estado global, usar Pinia; Vuex es legacy en Vue 3

## Errores comunes de generación AI

- Usar `Vetur` en lugar de `Volar` en `.vscode/extensions.json` — Vetur no entiende Composition API
- Usar `vue-tsc` sin el flag `-b` en el script de build — no realiza type-checking de templates
- Olvidar `env.d.ts` — `import.meta.env.VITE_*` tiene error de tipo `any`
- Usar Options API (`data()`, `methods:`, `computed:`) cuando el proyecto debería usar Composition API
- `tsconfig.json` monolítico en lugar del patrón de tres archivos — Vite requiere separación
- No instalar `@vitejs/plugin-vue` o no configurarlo en `vite.config.ts` — los archivos `.vue` no se procesan
- Usar `Vuex` en lugar de `Pinia` para estado global en proyectos Vue 3 nuevos
- Props sin tipar con `defineProps({})` en lugar de la forma genérica — pierde los beneficios de TypeScript
