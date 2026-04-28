# Build Infrastructure Checklist — TypeScript (Generic / Standalone)

Este archivo aplica cuando TypeScript se usa de forma standalone (sin framework específico) o como referencia de configuración base para proyectos Node.js + TypeScript que no son Express, NestJS, ni frontend.

Para frameworks específicos, ver:
- Node.js + Express + TypeScript → `skill_nodejs`
- NestJS → `skill_nestjs`
- React + Vite → `skill_react`
- Vue 3 + Vite → `skill_vue`
- Next.js → `skill_nextjs`
- Angular → `skill_angular`

## Archivos que SIEMPRE deben generarse en cualquier proyecto TypeScript

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar TypeScript ni correr scripts |
| `tsconfig.json` | Sin esto el compilador TypeScript no sabe cómo compilar |
| `.gitignore` | Debe excluir `node_modules/`, `dist/`, `.env` |

## tsconfig.json base recomendado (Node.js, CommonJS)

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
  "exclude": ["node_modules", "dist", "**/*.test.ts", "**/*.spec.ts"]
}
```

## tsconfig.json base recomendado (ESM / módulos modernos)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "sourceMap": true,
    "noEmit": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

## Opciones críticas de tsconfig explicadas

| Opción | Por qué importa |
|--------|----------------|
| `"strict": true` | Habilita `strictNullChecks`, `noImplicitAny`, `strictFunctionTypes`, etc. — mínimo requerido para código TypeScript seguro |
| `"esModuleInterop": true` | Permite `import express from 'express'` en lugar de `import * as express from 'express'` |
| `"skipLibCheck": true` | Evita errores de tipos en archivos `*.d.ts` de dependencias externas |
| `"sourceMap": true` | Mapea el JS compilado al TS original — indispensable para debug en VS Code |
| `"outDir"` / `"rootDir"` | Separa código fuente de compilado; `outDir` nunca debe ser igual a `rootDir` |
| `"declaration": true` | Genera archivos `.d.ts` — necesario si el proyecto es una librería |

## Reglas del auditor (checklist para código TypeScript generado)

1. **`strict: true` habilitado** — nunca generar proyectos con `"strict": false`; el modo no-estricto permite `any` implícito y `null` sin verificar
2. **Sin `any` explícito** — tipos de retorno y parámetros deben ser tipados; usar `unknown` cuando el tipo es realmente desconocido y hacer type narrowing
3. **`@types/*` en devDependencies** — paquetes de tipos de declaración nunca van en `dependencies`
4. **`sourceMap: true`** — sin sourcemaps el debug en VS Code no muestra el código TypeScript sino el JavaScript transpilado
5. **`outDir` en `.gitignore`** — el directorio de compilación (habitualmente `dist/`) nunca debe commitearse
6. **Imports sin extensión `.js` en CommonJS** — en módulos CommonJS los imports internos no llevan extensión; en ESM nativo sí deben llevar `.js`
7. **Interfaces para contratos de API, types para uniones/utilidades** — `interface` para shapes de objetos que se implementan; `type` para uniones, intersecciones y tipos utilitarios

## Errores comunes de generación AI en proyectos TypeScript

- Generar `tsconfig.json` sin `strict: true` — el mayor anti-patrón TypeScript
- Usar `any` en lugar de `unknown` para datos de fuentes externas (JSON de API, req.body)
- `@types/node`, `@types/express` en `dependencies` en lugar de `devDependencies`
- `outDir` igual a `rootDir` o no declarados — TypeScript compila pero los archivos quedan mezclados
- `module: "ESNext"` con `moduleResolution: "node"` — combinación incompatible desde TypeScript 5.0
- No incluir `sourceMap: true` — el debug en VS Code no funciona correctamente
- Usar `require()` en archivos `.ts` — TypeScript usa `import`; el compilador puede aceptarlo con `esModuleInterop` pero es inconsistente
