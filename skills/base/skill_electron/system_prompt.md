## Skill: Electron

You are building an Electron desktop application. Follow these conventions:

- Strict main/renderer/preload separation — never import `electron` directly in renderer
- Context isolation ENABLED (`contextIsolation: true`) — the preload script is the only bridge
- Node integration DISABLED in renderer (`nodeIntegration: false`) — security requirement
- IPC communication via `ipcMain.handle()` (main) + `ipcRenderer.invoke()` (preload/renderer)
- Preload script exposes a typed API via `contextBridge.exposeInMainWorld()`
- Use TypeScript for all three processes (main, renderer, preload)
- Vite + `electron-vite` (or `vite-plugin-electron`) for fast HMR development
- Packaging with `electron-builder` — generates installers for Windows, macOS, Linux
- Never use `shell.openExternal()` with unvalidated URLs — security risk
