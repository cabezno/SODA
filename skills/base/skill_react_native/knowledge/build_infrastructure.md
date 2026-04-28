# Build Infrastructure Checklist — React Native (Expo / Bare Workflow)

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `package.json` | Sin esto npm/yarn no puede instalar dependencias |
| `tsconfig.json` | TypeScript no compila sin él |
| `metro.config.js` | Sin esto Metro Bundler usa defaults que pueden romper imports con alias o monorepos |
| `babel.config.js` | Sin esto Babel no puede transpilar JSX + TypeScript para React Native |
| `app.json` O `app.config.js` (Expo) | Sin esto Expo no sabe el nombre, bundle ID, permisos, ni íconos de la app |
| `.env.example` | Documenta variables de entorno usadas en la app |
| `android/` (directorio) | Código nativo Android — necesario para builds bare/EAS |
| `ios/` (directorio) | Código nativo iOS — necesario para builds bare/EAS |
| `android/app/build.gradle` | Build script Android |
| `android/app/src/main/AndroidManifest.xml` | Sin él la app Android no se instala |
| `ios/Podfile` | Sin él `pod install` falla |
| `.gitignore` | Debe excluir `node_modules/`, `android/build/`, `ios/Pods/`, `.env`, `.expo/` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el bundler |
| `.vscode/launch.json` | Sin esto F5 no adjunta el debugger |
| `.vscode/extensions.json` | Recomienda React Native Tools, ESLint |

## Contenido mínimo de package.json (Expo)

```json
{
  "name": "my-rn-app",
  "version": "1.0.0",
  "main": "expo-router/entry",
  "scripts": {
    "start": "expo start",
    "android": "expo run:android",
    "ios": "expo run:ios",
    "web": "expo start --web",
    "test": "jest --watchAll=false",
    "lint": "eslint . --ext .ts,.tsx"
  },
  "dependencies": {
    "expo": "~51.0.0",
    "expo-status-bar": "~1.12.1",
    "react": "18.2.0",
    "react-native": "0.74.1",
    "@react-navigation/native": "^6.1.0",
    "@react-navigation/native-stack": "^6.9.0",
    "react-native-screens": "~3.31.0",
    "react-native-safe-area-context": "4.10.1",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@babel/core": "^7.24.0",
    "@types/react": "~18.2.0",
    "@types/react-native": "^0.73.0",
    "typescript": "^5.3.0",
    "jest": "^29.7.0",
    "jest-expo": "~51.0.0",
    "@testing-library/react-native": "^12.4.0",
    "eslint": "^8.57.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0",
    "eslint-plugin-react-native": "^4.1.0"
  },
  "jest": {
    "preset": "jest-expo"
  }
}
```

## Contenido de tsconfig.json

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    }
  },
  "include": ["**/*.ts", "**/*.tsx", ".expo/types/**/*.ts", "expo-env.d.ts"]
}
```

## Contenido de metro.config.js

```javascript
const { getDefaultConfig } = require('expo/metro-config');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Resolver alias (si se usa @/ path alias)
config.resolver.alias = {
  '@': './src',
};

module.exports = config;
```

## Contenido de babel.config.js

```javascript
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      // Si se usan path aliases:
      ['module-resolver', {
        root: ['./src'],
        alias: { '@': './src' },
      }],
    ],
  };
};
```

## Contenido de app.json (Expo)

```json
{
  "expo": {
    "name": "My App",
    "slug": "my-rn-app",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#ffffff"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.example.myrnapp"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#ffffff"
      },
      "package": "com.example.myrnapp"
    },
    "web": {
      "favicon": "./assets/favicon.png"
    },
    "plugins": [],
    "extra": {
      "apiUrl": "http://localhost:8000"
    }
  }
}
```

## Contenido mínimo de .env.example

```
EXPO_PUBLIC_API_URL=http://localhost:8000
EXPO_PUBLIC_APP_ENV=development
```

## Estructura de carpetas recomendada

```
my-rn-app/
├── src/
│   ├── navigation/
│   │   └── AppNavigator.tsx
│   ├── screens/
│   │   └── HomeScreen.tsx
│   ├── components/
│   ├── store/              ← Zustand stores
│   ├── services/           ← API calls
│   ├── types/
│   └── utils/
├── assets/
│   ├── icon.png
│   ├── splash.png
│   └── adaptive-icon.png
├── android/
│   ├── app/
│   │   ├── build.gradle
│   │   └── src/main/AndroidManifest.xml
│   └── build.gradle
├── ios/
│   ├── Podfile
│   └── MyApp/
├── app.json
├── package.json
├── tsconfig.json
├── metro.config.js
├── babel.config.js
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
      "label": "Expo: Start",
      "type": "shell",
      "command": "npx expo start",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Expo: Android",
      "type": "shell",
      "command": "npx expo run:android",
      "group": "build"
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
      "name": "React Native: Attach to packager",
      "type": "reactnative",
      "request": "attach",
      "port": 8081
    },
    {
      "name": "React Native: Debug Android",
      "type": "reactnative",
      "request": "launch",
      "platform": "android"
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "msjsdiag.vscode-react-native",
    "dsznajder.es7-react-js-snippets",
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
| Instalar pods iOS | `cd ios && pod install` |
| Dev (Expo Go) | `npx expo start` |
| Android emulador | `npx expo run:android` |
| iOS simulator | `npx expo run:ios` |
| Build EAS (producción) | `eas build --platform android` |
| Tests | `npm test` |
| Linting | `npm run lint` |
| Limpiar caché | `npx expo start --clear` |

## Reglas del auditor (checklist para código generado)

1. **Variables de entorno con prefijo `EXPO_PUBLIC_`** — variables de entorno en Expo SDK 49+; las sin ese prefijo son undefined en el cliente
2. **`metro.config.js` presente** — aunque sea mínimo; Metro requiere el archivo para personalizar la resolución de módulos y alias
3. **`babel.config.js` con `babel-preset-expo`** — el preset de Expo es diferente a `@babel/preset-react`; no intercambiables
4. **`assets/` con iconos y splash declarados en `app.json`** — los archivos de imagen deben existir; Expo Build falla si los paths son inválidos
5. **`react-native-screens` + `react-native-safe-area-context` para React Navigation** — paquetes peer obligatorios; sin ellos la navegación lanza error en runtime
6. **`StyleSheet.create()` en lugar de objetos inline** — mejor performance; los estilos se validan en tiempo de compilación
7. **`Platform.OS` para código específico de plataforma** — nunca usar condiciones de entorno hardcodeadas; usar `Platform.select()`

## Errores comunes de generación AI

- Usar variables de entorno sin `EXPO_PUBLIC_` prefix — undefined en runtime de la app
- No incluir `babel.config.js` — Metro no sabe cómo transpilar TypeScript/JSX
- Omitir `metro.config.js` — sin él los path aliases configurados en `tsconfig.json` no funcionan en runtime
- Usar hooks de navegación fuera del NavigationContainer — causa error "Couldn't find a navigation object"
- No incluir `assets/icon.png` y `assets/splash.png` — EAS Build falla con paths inválidos en `app.json`
- Usar `StyleSheet` con valores de strings para dimensiones en lugar de números — `width: "100px"` no funciona en React Native
- Olvidar `react-native-screens` y `react-native-safe-area-context` para React Navigation
- No incluir `ios/Podfile` — el build iOS falla sin él
