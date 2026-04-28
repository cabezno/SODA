# Build Infrastructure Checklist — Electron

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm no puede instalar Electron ni correr scripts |
| `electron.vite.config.ts` O `vite.config.ts` | Sin configuración de Vite, el bundler no sabe cómo compilar main/preload/renderer |
| `tsconfig.json` | TypeScript no compila sin él |
| `tsconfig.node.json` | Configuración TypeScript para main y preload (entorno Node) |
| `tsconfig.web.json` | Configuración TypeScript para el renderer (entorno DOM) |
| `src/main/index.ts` | Proceso principal de Electron — crea la BrowserWindow |
| `src/preload/index.ts` | Script de preload — único punto de comunicación seguro con el renderer |
| `src/renderer/index.html` | Template HTML del renderer |
| `src/renderer/src/main.ts` | Entry point del frontend (puede ser React/Vue/Vanilla) |
| `electron-builder.yml` O `electron-builder.json` | Sin este archivo `electron-builder` no sabe cómo empaquetar la app |
| `.env.example` | Variables de entorno para el proceso principal |
| `.gitignore` | Debe excluir `dist/`, `dist-electron/`, `node_modules/`, `.env`, `out/` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza Electron en modo dev |
| `.vscode/launch.json` | Sin esto F5 no adjunta el debugger al proceso principal |
| `.vscode/extensions.json` | Recomienda extensiones TypeScript, ESLint |

## Contenido mínimo de package.json (con electron-vite)

```json
{
  "name": "my-electron-app",
  "version": "1.0.0",
  "description": "",
  "main": "./out/main/index.js",
  "scripts": {
    "dev": "electron-vite dev",
    "build": "electron-vite build",
    "preview": "electron-vite preview",
    "package": "electron-vite build && electron-builder",
    "package:win": "electron-vite build && electron-builder --win",
    "package:mac": "electron-vite build && electron-builder --mac",
    "package:linux": "electron-vite build && electron-builder --linux",
    "test": "vitest run"
  },
  "dependencies": {
    "electron-updater": "^6.2.0"
  },
  "devDependencies": {
    "@electron-toolkit/eslint-config-ts": "^2.0.0",
    "@electron-toolkit/tsconfig": "^1.0.1",
    "@types/node": "^20.14.0",
    "electron": "^31.0.0",
    "electron-builder": "^24.13.0",
    "electron-vite": "^2.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.3.0",
    "vitest": "^1.6.0"
  }
}
```

## Contenido de electron.vite.config.ts

```typescript
import { resolve } from 'path'
import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'  // o vue() para Vue

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
  },
  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src'),
      },
    },
    plugins: [react()],  // o vue()
  },
})
```

## Contenido de tsconfig.json

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.node.json" },
    { "path": "./tsconfig.web.json" }
  ]
}
```

## Contenido de tsconfig.node.json

```json
{
  "extends": "@electron-toolkit/tsconfig/tsconfig.node.json",
  "include": ["electron.vite.config.*", "src/main/**/*", "src/preload/**/*"],
  "compilerOptions": {
    "composite": true,
    "types": ["electron-vite/node"]
  }
}
```

## Contenido de tsconfig.web.json

```json
{
  "extends": "@electron-toolkit/tsconfig/tsconfig.web.json",
  "include": ["src/renderer/src/**/*"],
  "compilerOptions": {
    "composite": true,
    "baseUrl": ".",
    "paths": {
      "@renderer/*": ["src/renderer/src/*"]
    }
  }
}
```

## Contenido de src/main/index.ts

```typescript
import { app, BrowserWindow, shell, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 900,
    height: 670,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,      // OBLIGATORIO
      nodeIntegration: false,      // OBLIGATORIO desactivar
    },
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.example.myapp')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
```

## Contenido de src/preload/index.ts

```typescript
import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// API tipada expuesta al renderer
const api = {
  // Ejemplo de canal IPC:
  openFile: (): Promise<string | null> => ipcRenderer.invoke('dialog:openFile'),
  onFileOpened: (callback: (path: string) => void) =>
    ipcRenderer.on('file:opened', (_event, path) => callback(path)),
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (solo en contextos sin isolation — no usar en producción)
  window.electron = electronAPI
  // @ts-ignore
  window.api = api
}
```

## Contenido de electron-builder.yml

```yaml
appId: com.example.myapp
productName: MyApp
copyright: Copyright © 2024 ${author}

directories:
  buildResources: build
  output: dist

files:
  - '!**/.vscode/*'
  - '!src/*'
  - '!electron.vite.config.{js,ts,mjs,cjs}'
  - '!{.eslintignore,.eslintrc.cjs,.prettierignore,.prettierrc.yaml,dev-app-update.yml,CHANGELOG.md,README.md}'
  - '!{.env,.env.*,.npmrc,pnpm-lock.yaml}'
  - '!{tsconfig.json,tsconfig.*}'
  - '!test'

win:
  executableName: myapp
nsis:
  artifactName: ${name}-${version}-setup.${ext}
  shortcutName: ${productName}
  uninstallDisplayName: ${productName}
  createDesktopShortcut: always

mac:
  entitlementsInherit: build/entitlements.mac.plist
  extendInfo:
    - NSCameraUsageDescription: Application requests access to the device's camera.
  notarize: false

dmg:
  artifactName: ${name}-${version}.${ext}

linux:
  target:
    - AppImage
    - snap
    - deb
  maintainer: electronjs.org
  category: Utility
appImage:
  artifactName: ${name}-${version}.${ext}
npmRebuild: false
publish:
  provider: generic
  url: https://example.com/auto-updates
```

## Estructura de carpetas

```
my-electron-app/
├── src/
│   ├── main/
│   │   └── index.ts            ← proceso principal
│   ├── preload/
│   │   ├── index.ts            ← script de preload
│   │   └── index.d.ts          ← tipos del API expuesto
│   └── renderer/
│       ├── index.html
│       └── src/
│           ├── main.ts         ← entry de React/Vue
│           ├── App.tsx
│           └── components/
├── build/                      ← recursos para electron-builder (iconos, etc.)
│   ├── icon.ico
│   ├── icon.icns
│   └── icon.png
├── electron.vite.config.ts
├── electron-builder.yml
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── tsconfig.web.json
├── .env.example
└── .gitignore
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
      "label": "Electron: Dev",
      "type": "shell",
      "command": "npm run dev",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Electron: Build",
      "type": "shell",
      "command": "npm run build",
      "group": "build"
    },
    {
      "label": "Electron: Package",
      "type": "shell",
      "command": "npm run package",
      "group": "build"
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
      "name": "Electron: Main Process",
      "type": "node",
      "request": "launch",
      "cwd": "${workspaceFolder}",
      "runtimeExecutable": "${workspaceFolder}/node_modules/.bin/electron",
      "windows": {
        "runtimeExecutable": "${workspaceFolder}/node_modules/.bin/electron.cmd"
      },
      "args": [".", "--remote-debugging-port=9229"],
      "sourceMaps": true,
      "outFiles": ["${workspaceFolder}/out/**/*.js"],
      "preLaunchTask": "Electron: Build"
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
    "esbenp.prettier-vscode"
  ]
}
```

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar deps | `npm install` |
| Dev mode | `npm run dev` |
| Build | `npm run build` |
| Empaquetar todos | `npm run package` |
| Empaquetar Windows | `npm run package:win` |
| Empaquetar macOS | `npm run package:mac` |
| Empaquetar Linux | `npm run package:linux` |

## Reglas del auditor (checklist para código generado)

1. **`contextIsolation: true` y `nodeIntegration: false`** — obligatorios por seguridad; sin contextIsolation el renderer puede acceder APIs de Node directamente (vulnerabilidad XSS → RCE)
2. **Nunca importar `electron` en el renderer** — el renderer es una página web; acceso a Electron solo mediante el preload y `contextBridge`
3. **`contextBridge.exposeInMainWorld()` tipado** — debe existir `src/preload/index.d.ts` con la declaración `interface Window { api: ... }` para que TypeScript reconozca el API en el renderer
4. **IPC con `ipcMain.handle()` + `ipcRenderer.invoke()`** — patrón async; evitar `ipcRenderer.sendSync()` que bloquea el proceso renderer
5. **`electron-builder.yml` con `appId` real** — el `appId` debe seguir el formato `com.company.appname`; sin él el empaquetado en macOS falla
6. **Íconos en `build/`** — `electron-builder` requiere `icon.ico` (Windows), `icon.icns` (macOS), `icon.png` (Linux); sin ellos el build usa un ícono placeholder
7. **`main` en `package.json` apunta al build compilado** — debe ser `./out/main/index.js`, no el source TypeScript

## Errores comunes de generación AI

- `nodeIntegration: true` — el error de seguridad más crítico; permite XSS → ejecución de código en sistema
- No usar `contextBridge` — el renderer importa directamente `require('electron')` que falla con contextIsolation
- Olvidar `src/preload/index.d.ts` — TypeScript no reconoce `window.api` en el renderer
- `electron-builder.yml` sin íconos referenciados correctamente — build produce app sin ícono o falla
- No separar tsconfig para main/preload (Node) y renderer (DOM) — errores de tipos mezclados
- `package.json` con `"main"` apuntando al `.ts` en lugar del `.js` compilado — Electron no puede cargar TypeScript directamente
- No incluir `electron-vite` o similar — el setup manual de Vite para tres procesos es complejo y propenso a errores
- Olvidar `app.whenReady()` antes de crear la ventana — la app lanza error en algunas plataformas
