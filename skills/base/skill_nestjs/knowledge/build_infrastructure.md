# Build Infrastructure Checklist — NestJS

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar dependencias ni correr scripts |
| `tsconfig.json` | Sin esto TypeScript no compila |
| `tsconfig.build.json` | NestJS requiere un tsconfig separado para build que excluye tests |
| `nest-cli.json` | Sin esto `nest build` y `nest start` no saben dónde está el código fuente |
| `.env.example` | Documenta todas las variables de entorno requeridas |
| `.env` | Variables reales en local (nunca commitear) |
| `.gitignore` | Debe excluir `node_modules/`, `dist/`, `.env` |
| `src/main.ts` | Entry point con `NestFactory.create()` y `app.listen()` |
| `src/app.module.ts` | Módulo raíz; todos los módulos se importan aquí |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el servidor |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger |
| `.vscode/extensions.json` | Recomienda extensiones NestJS, TypeScript |

## Contenido mínimo de package.json

```json
{
  "name": "my-nest-app",
  "version": "1.0.0",
  "scripts": {
    "build": "nest build",
    "start": "node dist/main",
    "start:dev": "nest start --watch",
    "start:debug": "nest start --debug --watch",
    "start:prod": "node dist/main",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:cov": "jest --coverage",
    "lint": "eslint \"{src,apps,libs,test}/**/*.ts\" --fix"
  },
  "dependencies": {
    "@nestjs/common": "^10.0.0",
    "@nestjs/core": "^10.0.0",
    "@nestjs/platform-express": "^10.0.0",
    "@nestjs/config": "^3.0.0",
    "reflect-metadata": "^0.2.0",
    "rxjs": "^7.8.0",
    "class-validator": "^0.14.0",
    "class-transformer": "^0.5.0"
  },
  "devDependencies": {
    "@nestjs/cli": "^10.0.0",
    "@nestjs/schematics": "^10.0.0",
    "@nestjs/testing": "^10.0.0",
    "@types/express": "^4.17.21",
    "@types/jest": "^29.5.0",
    "@types/node": "^20.0.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "eslint": "^8.57.0",
    "jest": "^29.7.0",
    "source-map-support": "^0.5.21",
    "ts-jest": "^29.1.0",
    "ts-loader": "^9.5.0",
    "ts-node": "^10.9.0",
    "tsconfig-paths": "^4.2.0",
    "typescript": "^5.4.0"
  },
  "jest": {
    "moduleFileExtensions": ["js", "json", "ts"],
    "rootDir": "src",
    "testRegex": ".*\\.spec\\.ts$",
    "transform": { "^.+\\.(t|j)s$": "ts-jest" },
    "coverageDirectory": "../coverage",
    "testEnvironment": "node"
  }
}
```

## Contenido mínimo de tsconfig.json

```json
{
  "compilerOptions": {
    "module": "commonjs",
    "declaration": true,
    "removeComments": true,
    "emitDecoratorMetadata": true,
    "experimentalDecorators": true,
    "allowSyntheticDefaultImports": true,
    "target": "ES2021",
    "sourceMap": true,
    "outDir": "./dist",
    "baseUrl": "./",
    "incremental": true,
    "skipLibCheck": true,
    "strictNullChecks": false,
    "noImplicitAny": false,
    "strictBindCallApply": false,
    "forceConsistentCasingInFileNames": false,
    "noFallthroughCasesInSwitch": false
  }
}
```

## Contenido de tsconfig.build.json

```json
{
  "extends": "./tsconfig.json",
  "exclude": ["node_modules", "test", "dist", "**/*spec.ts"]
}
```

## Contenido de nest-cli.json

```json
{
  "$schema": "https://json.schemastore.org/nest-cli",
  "collection": "@nestjs/schematics",
  "sourceRoot": "src",
  "compilerOptions": {
    "deleteOutDir": true
  }
}
```

## Contenido mínimo de .env.example

```
NODE_ENV=development
PORT=3000
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
JWT_SECRET=changeme_generate_random_32_chars
JWT_EXPIRATION=3600s
```

## Estructura de carpetas obligatoria

```
src/
├── main.ts                  ← NestFactory.create + bootstrap + ValidationPipe global
├── app.module.ts            ← módulo raíz con ConfigModule.forRoot({ isGlobal: true })
├── app.controller.ts        ← healthcheck GET /
├── app.service.ts
└── [feature]/
    ├── [feature].module.ts
    ├── [feature].controller.ts
    ├── [feature].service.ts
    ├── dto/
    │   ├── create-[feature].dto.ts
    │   └── update-[feature].dto.ts
    └── entities/
        └── [feature].entity.ts
```

## Contenido mínimo de src/main.ts

```typescript
import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { ValidationPipe } from '@nestjs/common';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  await app.listen(process.env.PORT ?? 3000);
}

bootstrap();
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
      "label": "NestJS: Build",
      "type": "shell",
      "command": "npm run build",
      "group": { "kind": "build", "isDefault": true },
      "problemMatcher": ["$tsc"]
    },
    {
      "label": "NestJS: Dev",
      "type": "shell",
      "command": "npm run start:dev",
      "group": "build",
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "NestJS: Test",
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
      "name": "NestJS: Debug",
      "type": "node",
      "request": "launch",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["run", "start:debug"],
      "sourceMaps": true,
      "outFiles": ["${workspaceFolder}/dist/**/*.js"],
      "console": "integratedTerminal",
      "restart": true
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

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar deps | `npm install` |
| Dev server | `npm run start:dev` |
| Debug | `npm run start:debug` |
| Build | `npm run build` |
| Producción | `npm run start:prod` |
| Tests | `npm test` |
| Tests con coverage | `npm run test:cov` |
| Generar módulo | `nest g module feature` |
| Generar controller | `nest g controller feature` |
| Generar service | `nest g service feature` |

## Reglas del auditor (checklist para código generado)

1. **`emitDecoratorMetadata: true` en tsconfig** — obligatorio para que los decoradores NestJS (`@Injectable`, `@Controller`, etc.) funcionen; sin esto el DI container falla silenciosamente
2. **`reflect-metadata` como primera importación en `main.ts`** — debe ser la primera línea antes de cualquier otro import NestJS
3. **Cada módulo declara sus controllers y providers** — las clases deben estar en los arrays `providers`/`controllers` del módulo propio, no solo en AppModule
4. **`class-validator` + `class-transformer` en `dependencies` (no devDependencies)** — son runtime; `ValidationPipe` los necesita en producción
5. **`ConfigModule.forRoot({ isGlobal: true })` en AppModule** — con `isGlobal: true` el `ConfigService` se inyecta en cualquier módulo sin re-importar `ConfigModule`
6. **`nest-cli.json` presente** — sin esto `nest build` y `nest start --watch` no funcionan
7. **`ValidationPipe` global con `whitelist: true`** — sin esto los DTOs aceptan propiedades extra no declaradas, riesgo de seguridad
8. **Tests `.spec.ts` al lado del código** — NestJS espera `*.spec.ts` en el mismo directorio que el archivo testeado; el Jest config tiene `rootDir: "src"`

## Errores comunes de generación AI

- Olvidar `emitDecoratorMetadata: true` en tsconfig — el DI container falla silenciosamente con errores crípticos
- Olvidar `import 'reflect-metadata'` en `main.ts` — causa errores de metadata en decoradores
- No declarar el servicio en `providers` del módulo — resulta en "Nest can't resolve dependencies of the XService"
- Usar `tsconfig.json` sin `tsconfig.build.json` — `nest build` incluye archivos `.spec.ts` en el bundle de producción
- Omitir `nest-cli.json` — los comandos `nest start`, `nest build`, `nest g` no funcionan
- Poner `class-validator` y `class-transformer` en devDependencies — son dependencias de runtime para `ValidationPipe`
- No agregar `ValidationPipe` global en `main.ts` — las anotaciones `@IsString()` en DTOs no hacen nada
- No usar `@nestjs/config` para variables de entorno — leer `process.env` directamente sin módulo de config ni tipado
