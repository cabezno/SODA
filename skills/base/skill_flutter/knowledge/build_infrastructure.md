# Build Infrastructure Checklist — Flutter / Dart

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `pubspec.yaml` | Sin esto `flutter pub get` no puede instalar paquetes ni el Flutter SDK no puede compilar |
| `pubspec.lock` | Debe commitearse; garantiza versiones exactas de paquetes |
| `analysis_options.yaml` | Sin esto no hay linting; el código generado puede tener warnings críticos |
| `lib/main.dart` | Entry point de la app: `void main() => runApp(MyApp())` |
| `android/app/build.gradle` | Build script del módulo Android; sin él la compilación Android falla |
| `android/app/src/main/AndroidManifest.xml` | Sin este manifiesto Android no puede registrar la app |
| `android/local.properties` | Apunta al SDK de Android y Flutter; necesario para el build Android. NUNCA commitear |
| `ios/Podfile` | Sin él `pod install` falla y la compilación iOS no puede resolver dependencias |
| `.gitignore` | Debe excluir `build/`, `.dart_tool/`, `android/local.properties`, `ios/Pods/`, `*.g.dart` (si se usa code gen) |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el app |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger de Flutter |
| `.vscode/extensions.json` | Recomienda extensión Flutter oficial |

## Contenido mínimo de pubspec.yaml

```yaml
name: my_flutter_app
description: "A Flutter application"
publish_to: 'none'

version: 1.0.0+1

environment:
  sdk: '>=3.3.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter

  # UI
  cupertino_icons: ^1.0.8

  # Navigation
  go_router: ^14.0.0

  # State management
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0

  # Network
  dio: ^5.4.0

  # Local storage
  shared_preferences: ^2.2.0

  # Utils
  freezed_annotation: ^2.4.0
  json_annotation: ^4.9.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^4.0.0
  build_runner: ^2.4.0
  riverpod_generator: ^2.4.0
  freezed: ^2.5.0
  json_serializable: ^6.8.0

flutter:
  uses-material-design: true

  assets:
    - assets/images/
    - assets/icons/

  fonts:
    []  # Agregar fuentes personalizadas aquí
```

## Contenido de analysis_options.yaml

```yaml
include: package:flutter_lints/flutter.yaml

linter:
  rules:
    - always_declare_return_types
    - avoid_print
    - prefer_const_constructors
    - prefer_const_declarations
    - prefer_final_fields
    - require_trailing_commas
    - sort_child_properties_last

analyzer:
  errors:
    invalid_annotation_target: ignore  # para freezed
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"
```

## Contenido de android/app/build.gradle

```groovy
plugins {
    id "com.android.application"
    id "kotlin-android"
    id "dev.flutter.flutter-gradle-plugin"
}

android {
    namespace = "com.example.myflutterapp"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        jvmTarget = '1.8'
    }

    defaultConfig {
        applicationId = "com.example.myflutterapp"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.debug
        }
    }
}

flutter {
    source = '../..'
}
```

## Contenido de ios/Podfile

```ruby
# Uncomment the next line to define a global platform for your project
platform :ios, '12.0'

# CocoaPods analytics sends network stats synchronously affecting flutter build latency.
ENV['COCOAPODS_DISABLE_STATS'] = 'true'

project 'Runner', {
  'Debug' => :debug,
  'Profile' => :release,
  'Release' => :release,
}

def flutter_root
  generated_xcode_build_settings_path = File.expand_path(File.join('..', 'Flutter', 'Generated.xcconfig'), __FILE__)
  unless File.exist?(generated_xcode_build_settings_path)
    raise "#{generated_xcode_build_settings_path} must exist. Run flutter pub get first."
  end

  File.foreach(generated_xcode_build_settings_path) do |line|
    matches = line.match(/FLUTTER_ROOT\=(.*)/)
    return matches[1].strip if matches
  end
  raise "FLUTTER_ROOT not found in #{generated_xcode_build_settings_path}."
end

require File.expand_path(File.join('packages', 'flutter_tools', 'bin', 'podhelper'), flutter_root)

flutter_ios_podfile_setup

target 'Runner' do
  use_frameworks!
  use_modular_headers!

  flutter_install_all_ios_pods File.dirname(File.realpath(__FILE__))
  target 'RunnerTests' do
    inherit! :search_paths
  end
end

post_install do |installer|
  installer.pods_project.targets.each do |target|
    flutter_additional_ios_build_settings(target)
  end
end
```

## Estructura de carpetas recomendada

```
my_flutter_app/
├── lib/
│   ├── main.dart                   ← entry point
│   ├── app.dart                    ← MaterialApp + GoRouter + ProviderScope
│   ├── features/
│   │   └── [feature]/
│   │       ├── data/
│   │       │   ├── models/
│   │       │   └── repositories/
│   │       ├── domain/
│   │       └── presentation/
│   │           ├── screens/
│   │           ├── widgets/
│   │           └── providers/  (Riverpod)
│   └── core/
│       ├── router/
│       ├── theme/
│       └── utils/
├── assets/
│   ├── images/
│   └── icons/
├── android/
│   ├── app/
│   │   ├── build.gradle
│   │   └── src/main/AndroidManifest.xml
│   └── local.properties             ← NUNCA commitear
├── ios/
│   ├── Podfile
│   └── Runner/
├── test/
├── pubspec.yaml
├── pubspec.lock
├── analysis_options.yaml
└── .gitignore
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Flutter: pub get",
      "type": "shell",
      "command": "flutter pub get",
      "group": "build"
    },
    {
      "label": "Flutter: Run",
      "type": "shell",
      "command": "flutter run",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Flutter: Build APK",
      "type": "shell",
      "command": "flutter build apk --release",
      "group": "build"
    },
    {
      "label": "Flutter: Test",
      "type": "shell",
      "command": "flutter test",
      "group": { "kind": "test", "isDefault": true }
    },
    {
      "label": "Flutter: Build runner",
      "type": "shell",
      "command": "dart run build_runner build --delete-conflicting-outputs",
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
      "name": "Flutter: Debug",
      "request": "launch",
      "type": "dart",
      "program": "lib/main.dart",
      "args": ["--flavor", "development", "--dart-define=ENV=development"]
    },
    {
      "name": "Flutter: Profile",
      "request": "launch",
      "type": "dart",
      "flutterMode": "profile",
      "program": "lib/main.dart"
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "Dart-Code.flutter",
    "Dart-Code.dart-code"
  ]
}
```

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar paquetes | `flutter pub get` |
| Dev (dispositivo conectado) | `flutter run` |
| Build APK debug | `flutter build apk` |
| Build APK release | `flutter build apk --release` |
| Build iOS | `flutter build ios --release` |
| Build web | `flutter build web` |
| Tests | `flutter test` |
| Análisis de código | `flutter analyze` |
| Code generation | `dart run build_runner build --delete-conflicting-outputs` |
| Limpiar build | `flutter clean` |

## Reglas del auditor (checklist para código generado)

1. **Null safety habilitado** — `sdk: '>=3.3.0 <4.0.0'` en pubspec.yaml; todas las variables deben tener tipos explícitos o inferidos no-nullables
2. **`pubspec.lock` commiteado** — garantiza reproducibilidad; no debe estar en `.gitignore`
3. **Assets declarados en `pubspec.yaml`** — todo archivo en `assets/` debe estar listado en la sección `flutter.assets`; de lo contrario `AssetImage()` falla en runtime
4. **No usar `BuildContext` después de `await` sin chequear `mounted`** — el widget puede haberse desmontado; usar `if (!mounted) return;` antes de cualquier uso del context post-async
5. **`android/local.properties` en `.gitignore`** — contiene paths locales del SDK; específico de cada máquina
6. **Code-gen ejecutado** — si se usan `freezed`, `json_serializable`, o `riverpod_generator`, los archivos `.g.dart` y `.freezed.dart` deben generarse con `build_runner`
7. **`analysis_options.yaml` con `flutter_lints`** — mínimo requerido para calidad de código

## Errores comunes de generación AI

- Olvidar declarar assets en `pubspec.yaml` — `Image.asset()` lanza `FlutterError` en runtime
- No ejecutar `build_runner` cuando se usan `freezed` o `riverpod_generator` — los archivos `.g.dart` son ausentes y el proyecto no compila
- Usar `setState` para estado de negocio en lugar de Riverpod/BLoC
- Usar `BuildContext` después de `await` sin verificar `mounted` — crash en widgets desmontados
- `pubspec.lock` en `.gitignore` — rompe reproducibilidad
- Olvidar `analysis_options.yaml` — sin linting se generan antipatrones sin warnings
- Usar `Navigator.push()` en lugar de `go_router` cuando el proyecto usa go_router
- No incluir `ios/Podfile` — el build iOS falla en la primera vez sin `pod install`
