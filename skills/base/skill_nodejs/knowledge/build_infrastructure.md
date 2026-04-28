# Build Infrastructure Checklist — Node.js + TypeScript

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar dependencias ni correr scripts |
| `tsconfig.json` | Sin esto TypeScript no compila |
| `.env.example` | Documenta todas las variables de entorno requeridas |
| `.env` | Variables reales en local (nunca commitear) |
| `.gitignore` | Debe excluir `node_modules/`, `dist/`, `.env` |
| `src/index.ts` | Entry point de la aplicación |
| `nodemon.json` | Sin esto `nodemon` no sabe qué archivos observar ni cómo compilar |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el servidor |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger con source maps correctos |
| `.vscode/extensions.json` | Recomienda extensiones TypeScript y REST Client |

## Contenido mínimo de package.json

```json
{
  "name": "my-ts-app",
  "version": "1.0.0",
  "description": "",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "dev": "nodemon",
    "start": "node dist/index.js",
    "test": "jest --coverage",
    "lint": "eslint src --ext .ts"
  },
  "dependencies": {
    "express": "^4.19.0",
    "dotenv": "^16.4.0",
    "cors": "^2.8.5"
  },
  "devDependencies": {
    "@types/express": "^4.17.21",
    "@types/cors": "^2.8.17",
    "@types/node": "^20.0.0",
    "typescript": "^5.4.0",
    "nodemon": "^3.1.0",
    "ts-node": "^10.9.0",
    "jest": "^29.7.0",
    "@types/jest": "^29.5.0",
    "ts-jest": "^29.1.0",
    "eslint": "^8.57.0",
    "@typescript-eslint/parser": "^7.0.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0"
  }
}
```

## Contenido mínimo de tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "**/*.test.ts"]
}
```

## Contenido de nodemon.json

```json
{
  "watch": ["src"],
  "ext": ".ts,.js",
  "ignore": [],
  "exec": "ts-node ./src/index.ts"
}
```

## Contenido mínimo de .env.example

```
NODE_ENV=development
PORT=3000
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
JWT_SECRET=changeme_generate_random_32_chars
ALLOWED_ORIGINS=http://localhost:5173
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
      "label": "Build TypeScript",
      "type": "shell",
      "command": "npm run build",
      "group": { "kind": "build", "isDefault": true },
      "problemMatcher": ["$tsc"]
    },
    {
      "label": "Run dev server",
      "type": "shell",
      "command": "npm run dev",
      "group": "build",
      "presentation": { "reveal": "always", "panel": "dedicated" }
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
      "name": "Node.js: Debug (ts-node)",
      "type": "node",
      "request": "launch",
      "runtimeArgs": ["-r", "ts-node/register"],
      "args": ["${workspaceFolder}/src/index.ts"],
      "cwd": "${workspaceFolder}",
      "env": { "NODE_ENV": "development" },
      "sourceMaps": true,
      "console": "integratedTerminal"
    },
    {
      "name": "Node.js: Debug (compiled)",
      "type": "node",
      "request": "launch",
      "program": "${workspaceFolder}/dist/index.js",
      "preLaunchTask": "Build TypeScript",
      "sourceMaps": true,
      "outFiles": ["${workspaceFolder}/dist/**/*.js"],
      "console": "integratedTerminal"
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
    "humao.rest-client",
    "christian-kohler.npm-intellisense"
  ]
}
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar Node.js >= 20 LTS (https://nodejs.org/)
2. Instalar dependencias: `npm install`
3. Copiar `.env.example` a `.env` y completar valores reales
4. Correr servidor en modo desarrollo: `npm run dev`
5. Para producción: `npm run build && npm start`

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar deps | `npm install` |
| Dev server | `npm run dev` |
| Compilar | `npm run build` |
| Producción | `npm start` |
| Tests | `npm test` |
| Linting | `npm run lint` |

## Reglas del auditor (checklist para código generado)

1. **`strict: true` en tsconfig** — verificar que está habilitado; sin esto TypeScript no atrapa errores de tipos null/undefined
2. **Variables de entorno tipadas** — debe existir un archivo `src/config.ts` o `src/env.ts` que lea `process.env.*` y falle al inicio si alguna variable requerida está ausente
3. **`@types/*` en devDependencies** — cada paquete de tipos debe estar en `devDependencies`, no en `dependencies`
4. **`dist/` en .gitignore** — el directorio de compilación nunca debe commitearse
5. **`sourceMap: true` en tsconfig** — sin esto F5 no funciona correctamente para debug
6. **Error handling middleware de Express** — debe existir `(err, req, res, next) => {}` con 4 parámetros al final de los middlewares
7. **`ts-node` en devDependencies** — requerido para que `nodemon` ejecute TypeScript directamente; si falta, `npm run dev` falla

## Errores comunes de generación AI

- Usar `require()` en lugar de `import/export` (CommonJS en lugar de ESM/TypeScript nativo)
- Olvidar `@types/node` — sin esto `process`, `__dirname`, `Buffer` tienen error de tipo
- Poner `@types/*` en `dependencies` en lugar de `devDependencies`
- No incluir `nodemon.json` — sin él `nodemon` no sabe llamar `ts-node`
- Olvidar `sourceMap: true` en tsconfig — debug en VS Code no funciona correctamente
- No validar variables de entorno al inicio — la app arranca y falla tarde con errores confusos
- `outDir` y `rootDir` mal configurados en tsconfig — TypeScript compila pero los archivos quedan en lugares inesperados
- Usar `any` en lugar de tipar correctamente las respuestas de Express (`Request`, `Response`, `NextFunction`)
- Olvidar `esModuleInterop: true` — importaciones de módulos como `import express from 'express'` fallan sin esto
