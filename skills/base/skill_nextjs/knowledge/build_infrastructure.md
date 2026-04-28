# Build Infrastructure Checklist — Next.js

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar Next.js ni correr scripts |
| `next.config.js` O `next.config.mjs` O `next.config.ts` | Sin este archivo Next.js usa defaults que pueden no ser adecuados; es requerido para configurar redirects, rewrites, env, etc. |
| `tsconfig.json` | TypeScript no compila sin él; Next.js lo requiere y lo modifica automáticamente |
| `src/app/layout.tsx` (App Router) O `pages/_app.tsx` (Pages Router) | Entry point del layout global; sin él la app no arranca |
| `src/app/page.tsx` O `pages/index.tsx` | Ruta raíz (`/`); sin ella Next.js lanza error de página no encontrada |
| `.env.example` | Documenta variables de entorno públicas y privadas |
| `.env.local` | Variables reales de desarrollo; Next.js las carga automáticamente |
| `.gitignore` | Debe excluir `node_modules/`, `.next/`, `.env.local`, `.env.*.local` |
| `public/` | Directorio de assets estáticos; debe existir aunque esté vacío |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el dev server |
| `.vscode/launch.json` | Sin esto F5 no adjunta el debugger a Next.js |
| `.vscode/extensions.json` | Recomienda extensiones TypeScript, ESLint, Tailwind |

## Contenido mínimo de package.json

```json
{
  "name": "my-next-app",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "jest --coverage"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@types/jest": "^29.5.0",
    "typescript": "^5.5.0",
    "jest": "^29.7.0",
    "jest-environment-jsdom": "^29.7.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "eslint": "^8.57.0",
    "eslint-config-next": "^14.2.0"
  }
}
```

## Contenido de next.config.mjs

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Strict mode para detectar problemas en desarrollo
  reactStrictMode: true,

  // Exponer variables de entorno al cliente (solo las no-secretas)
  env: {
    NEXT_PUBLIC_APP_NAME: process.env.NEXT_PUBLIC_APP_NAME,
  },

  // Rewrites para proxear la API en desarrollo
  async rewrites() {
    return process.env.NODE_ENV === 'development'
      ? [
          {
            source: '/api/:path*',
            destination: `${process.env.BACKEND_URL}/api/:path*`,
          },
        ]
      : []
  },
}

export default nextConfig
```

## Contenido de tsconfig.json (App Router)

```json
{
  "compilerOptions": {
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [
      {
        "name": "next"
      }
    ],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

## Estructura de carpetas (App Router — recomendado)

```
my-next-app/
├── src/
│   ├── app/
│   │   ├── layout.tsx          ← RootLayout obligatorio
│   │   ├── page.tsx            ← ruta /
│   │   ├── globals.css
│   │   └── [feature]/
│   │       ├── page.tsx        ← ruta /feature
│   │       └── loading.tsx
│   ├── components/
│   ├── lib/                    ← utilities, API clients
│   └── types/
├── public/
├── next.config.mjs
├── tsconfig.json
├── package.json
├── .env.example
└── .gitignore
```

## Contenido mínimo de .env.example

```
# Variables públicas (accesibles en el browser — prefijo NEXT_PUBLIC_)
NEXT_PUBLIC_APP_NAME=MyApp
NEXT_PUBLIC_API_URL=http://localhost:8000

# Variables privadas (solo server-side)
BACKEND_URL=http://localhost:8000
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
JWT_SECRET=changeme_generate_random_32_chars
NEXTAUTH_SECRET=changeme_generate_random_32_chars
NEXTAUTH_URL=http://localhost:3000
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
      "label": "Next.js: Dev",
      "type": "shell",
      "command": "npm run dev",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Next.js: Build",
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
      "name": "Next.js: Debug full-stack",
      "type": "node",
      "request": "launch",
      "program": "${workspaceFolder}/node_modules/.bin/next",
      "args": ["dev"],
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal",
      "sourceMaps": true,
      "serverReadyAction": {
        "action": "openExternally",
        "pattern": "started server on .+, url: (https?://.+)"
      }
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "ms-vscode.vscode-typescript-next",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "dsznajder.es7-react-js-snippets"
  ]
}
```

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar deps | `npm install` |
| Dev server | `npm run dev` |
| Build | `npm run build` |
| Producción | `npm start` |
| Tests | `npm test` |
| Linting | `npm run lint` |

## Reglas del auditor (checklist para código generado)

1. **`NEXT_PUBLIC_` prefix para variables del cliente** — variables sin ese prefijo son undefined en el browser; variables con el prefijo son expuestas al bundle público, nunca usarlas para secretos
2. **`RootLayout` con `<html>` y `<body>` en App Router** — `src/app/layout.tsx` DEBE contener los tags `<html lang="...">` y `<body>`; de lo contrario Next.js lanza error de hidratación
3. **`"use client"` solo cuando necesario** — componentes del App Router son Server Components por defecto; agregar `"use client"` solo cuando se usan hooks, eventos o APIs del browser
4. **`next.config.mjs` con `reactStrictMode: true`** — detecta problemas de doble render en desarrollo
5. **`.next/` en `.gitignore`** — el directorio de build de Next.js nunca debe commitearse
6. **Metadata exportada desde `layout.tsx`** — debe existir `export const metadata: Metadata = { title: '...' }` en el layout raíz para SEO
7. **API Routes en `src/app/api/` (App Router)** — los archivos deben llamarse `route.ts` y exportar funciones HTTP: `export async function GET(request: Request) {}`

## Errores comunes de generación AI

- Mezclar App Router (`src/app/`) y Pages Router (`pages/`) en el mismo proyecto
- Usar `"use client"` en todos los componentes — anula los beneficios de Server Components
- Variables de entorno privadas accesibles desde componentes cliente (sin `NEXT_PUBLIC_`) — undefined en runtime del browser
- `RootLayout` sin `<html>` y `<body>` — Next.js lanza advertencia de hidratación
- `next.config.js` con sintaxis ESM cuando el proyecto usa CommonJS, o viceversa
- No incluir `eslint-config-next` — el linting de Next.js tiene reglas específicas para App Router
- API Routes con nombre `api.ts` en lugar de `route.ts` — el App Router no reconoce el archivo
- Olvidar `"use client"` en componentes que usan `useState`, `useEffect`, `onClick` — error de compilación
