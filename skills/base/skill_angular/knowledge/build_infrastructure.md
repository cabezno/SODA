# Build Infrastructure Checklist — Angular

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar Angular ni correr scripts |
| `angular.json` | Sin esto Angular CLI no sabe cómo compilar, testear ni hacer build del proyecto |
| `tsconfig.json` | Configuración base de TypeScript para todo el workspace |
| `tsconfig.app.json` | Configuración TypeScript específica para la aplicación (extiende tsconfig.json) |
| `tsconfig.spec.json` | Configuración TypeScript para los tests (extiende tsconfig.json) |
| `src/main.ts` | Entry point de la aplicación: `bootstrapApplication(AppComponent, appConfig)` |
| `src/app/app.component.ts` | Componente raíz de la aplicación |
| `src/app/app.config.ts` | Configuración de la app (proveedores, router, etc.) |
| `src/app/app.routes.ts` | Definición de rutas |
| `src/index.html` | Template HTML base con `<app-root>` |
| `src/styles.css` O `src/styles.scss` | Estilos globales |
| `src/environments/environment.ts` | Variables de entorno para desarrollo |
| `src/environments/environment.prod.ts` | Variables de entorno para producción |
| `.gitignore` | Debe excluir `node_modules/`, `dist/`, `.angular/` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el dev server |
| `.vscode/launch.json` | Sin esto F5 no abre Chrome con sourcemaps |
| `.vscode/extensions.json` | Recomienda Angular Language Service |

## Contenido mínimo de package.json

```json
{
  "name": "my-angular-app",
  "version": "0.0.0",
  "scripts": {
    "ng": "ng",
    "start": "ng serve",
    "build": "ng build",
    "watch": "ng build --watch --configuration development",
    "test": "ng test",
    "lint": "ng lint"
  },
  "private": true,
  "dependencies": {
    "@angular/animations": "^17.3.0",
    "@angular/common": "^17.3.0",
    "@angular/compiler": "^17.3.0",
    "@angular/core": "^17.3.0",
    "@angular/forms": "^17.3.0",
    "@angular/platform-browser": "^17.3.0",
    "@angular/platform-browser-dynamic": "^17.3.0",
    "@angular/router": "^17.3.0",
    "rxjs": "~7.8.0",
    "tslib": "^2.6.0",
    "zone.js": "~0.14.3"
  },
  "devDependencies": {
    "@angular-devkit/build-angular": "^17.3.0",
    "@angular/cli": "^17.3.0",
    "@angular/compiler-cli": "^17.3.0",
    "@types/jasmine": "~5.1.0",
    "jasmine-core": "~5.1.0",
    "karma": "~6.4.0",
    "karma-chrome-launcher": "~3.2.0",
    "karma-coverage": "~2.2.0",
    "karma-jasmine": "~5.1.0",
    "karma-jasmine-html-reporter": "~2.1.0",
    "typescript": "~5.4.0"
  }
}
```

## Contenido crítico de angular.json (esqueleto)

```json
{
  "$schema": "./node_modules/@angular/cli/lib/config/schema.json",
  "version": 1,
  "newProjectRoot": "projects",
  "projects": {
    "my-angular-app": {
      "projectType": "application",
      "schematics": {
        "@schematics/angular:component": {
          "style": "scss",
          "standalone": true,
          "changeDetection": "OnPush"
        }
      },
      "root": "",
      "sourceRoot": "src",
      "prefix": "app",
      "architect": {
        "build": {
          "builder": "@angular-devkit/build-angular:application",
          "options": {
            "outputPath": "dist/my-angular-app",
            "index": "src/index.html",
            "browser": "src/main.ts",
            "polyfills": ["zone.js"],
            "tsConfig": "tsconfig.app.json",
            "assets": ["src/favicon.ico", "src/assets"],
            "styles": ["src/styles.scss"],
            "scripts": []
          },
          "configurations": {
            "production": {
              "budgets": [
                { "type": "initial", "maximumWarning": "500kB", "maximumError": "1MB" },
                { "type": "anyComponentStyle", "maximumWarning": "2kB", "maximumError": "4kB" }
              ],
              "outputHashing": "all"
            },
            "development": {
              "optimization": false,
              "extractLicenses": false,
              "sourceMap": true
            }
          },
          "defaultConfiguration": "production"
        },
        "serve": {
          "builder": "@angular-devkit/build-angular:dev-server",
          "configurations": {
            "production": { "buildTarget": "my-angular-app:build:production" },
            "development": { "buildTarget": "my-angular-app:build:development" }
          },
          "defaultConfiguration": "development"
        },
        "test": {
          "builder": "@angular-devkit/build-angular:karma",
          "options": {
            "polyfills": ["zone.js", "zone.js/testing"],
            "tsConfig": "tsconfig.spec.json",
            "assets": ["src/favicon.ico", "src/assets"],
            "styles": ["src/styles.scss"],
            "scripts": []
          }
        }
      }
    }
  }
}
```

## Contenido de tsconfig.json

```json
{
  "compileOnSave": false,
  "compilerOptions": {
    "baseUrl": "./",
    "outDir": "./dist/out-tsc",
    "forceConsistentCasingInFileNames": true,
    "strict": true,
    "noImplicitOverride": true,
    "noPropertyAccessFromIndexSignature": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "sourceMap": true,
    "declaration": false,
    "experimentalDecorators": true,
    "moduleResolution": "bundler",
    "importHelpers": true,
    "target": "ES2022",
    "module": "ES2022",
    "useDefineForClassFields": false,
    "lib": ["ES2022", "dom"]
  },
  "angularCompilerOptions": {
    "enableI18nLegacyMessageIdFormat": false,
    "strictInjectionParameters": true,
    "strictInputAccessModifiers": true,
    "strictTemplates": true
  }
}
```

## Contenido de tsconfig.app.json

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "outDir": "./out-tsc/app",
    "types": []
  },
  "files": ["src/main.ts"],
  "include": ["src/**/*.d.ts"]
}
```

## Contenido de tsconfig.spec.json

```json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "outDir": "./out-tsc/spec",
    "types": ["jasmine"]
  },
  "include": ["src/**/*.spec.ts", "src/**/*.d.ts"]
}
```

## Contenido de src/main.ts (standalone, Angular 17+)

```typescript
import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

bootstrapApplication(AppComponent, appConfig).catch((err) =>
  console.error(err)
);
```

## Contenido de src/app/app.config.ts

```typescript
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withFetch()),
  ],
};
```

## Contenido mínimo de src/environments/environment.ts

```typescript
export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  appName: 'MyApp',
};
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
      "label": "Angular: Serve",
      "type": "shell",
      "command": "ng serve",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Angular: Build",
      "type": "shell",
      "command": "ng build",
      "group": "build",
      "problemMatcher": ["$tsc"]
    },
    {
      "label": "Angular: Test",
      "type": "shell",
      "command": "ng test",
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
      "name": "Chrome: Launch Angular",
      "type": "chrome",
      "request": "launch",
      "url": "http://localhost:4200",
      "webRoot": "${workspaceFolder}/src",
      "preLaunchTask": "Angular: Serve"
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "angular.ng-template",
    "dbaeumer.vscode-eslint",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next"
  ]
}
```

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar deps | `npm install` |
| Dev server | `ng serve` (o `npm start`) |
| Build prod | `ng build` |
| Tests | `ng test` |
| Tests headless | `ng test --no-watch --browsers=ChromeHeadless` |
| Linting | `ng lint` |
| Generar componente | `ng generate component my-feature --standalone` |

## Reglas del auditor (checklist para código generado)

1. **`angular.json` con `builder: "@angular-devkit/build-angular:application"`** — Angular 17+ usa el nuevo builder `application`; el antiguo `browser` está deprecado
2. **Componentes standalone** — todos los componentes deben tener `standalone: true` en Angular 17+; los que usen `@NgModule` son el patrón legacy
3. **`strictTemplates: true` en `angularCompilerOptions`** — detecta errores de tipo en templates HTML; sin esto los errores solo aparecen en runtime
4. **`provideHttpClient()` en `app.config.ts`** — no usar `HttpClientModule` (NgModule); en standalone usar el proveedor funcional
5. **Imports de módulos Angular en cada componente standalone** — `CommonModule`, `RouterModule`, `FormsModule` deben importarse individualmente en cada componente standalone que los necesite
6. **Environments con `fileReplacements` en `angular.json`** — el archivo `environment.prod.ts` debe estar configurado para ser sustituido en builds de producción
7. **`OnPush` change detection en componentes** — `changeDetection: ChangeDetectionStrategy.OnPush` mejora el performance; el componente debe ser puro o usar Signals/Observables

## Errores comunes de generación AI

- Usar `@NgModule` + `AppModule` (Angular 14 y anteriores) en lugar de standalone components
- Olvidar `angular.json` — sin él `ng serve` y `ng build` no funcionan
- No incluir los tres tsconfig (`tsconfig.json`, `tsconfig.app.json`, `tsconfig.spec.json`) — el build y los tests fallan
- Importar `HttpClientModule` en lugar de `provideHttpClient()` en proyectos standalone
- No declarar imports de Angular en componentes standalone — `*ngIf`, `routerLink` tienen error de compilación
- `angular.json` con el builder antiguo `@angular-devkit/build-angular:browser` en lugar de `application`
- No incluir `zone.js` en los polyfills del angular.json — la detección de cambios no funciona
- Environments sin `fileReplacements` — el build de producción usa las URLs de desarrollo
