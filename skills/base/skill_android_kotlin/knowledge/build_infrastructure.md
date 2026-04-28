# Build Infrastructure Checklist — Android (Kotlin + Gradle)

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `build.gradle.kts` (raíz) | Sin el build script de raíz, Gradle no puede configurar el proyecto |
| `app/build.gradle.kts` | Sin el build script del módulo app, no puede compilar la APK |
| `settings.gradle.kts` | Sin él Gradle no sabe qué módulos existen en el proyecto |
| `gradle/libs.versions.toml` | Version Catalog — centraliza versiones de dependencias; requerido desde AGP 8.x |
| `gradle/wrapper/gradle-wrapper.properties` | Define la versión de Gradle a usar; sin él `./gradlew` falla |
| `gradlew` + `gradlew.bat` | Gradle Wrapper — permite construir sin Gradle instalado globalmente |
| `app/src/main/AndroidManifest.xml` | Sin él Android no puede registrar la app ni sus componentes |
| `app/src/main/java/.../MainActivity.kt` | Activity principal — entry point de la app |
| `app/src/main/res/values/strings.xml` | Recursos de texto; evita hardcodear strings en el código |
| `local.properties` | Debe existir con `sdk.dir=...` apuntando al SDK local — NUNCA commitear |
| `.gitignore` | Debe excluir `local.properties`, `*.jks`, `build/`, `.gradle/`, `*.apk` |
| `README.md` | Sin instrucciones el usuario no sabe cómo compilar |

## Contenido de settings.gradle.kts

```kotlin
pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
    versionCatalogs {
        create("libs") {
            from(files("gradle/libs.versions.toml"))
        }
    }
}

rootProject.name = "MyApp"
include(":app")
```

## Contenido de build.gradle.kts (raíz)

```kotlin
// Top-level build file — no añadir dependencias de módulos aquí
plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
}
```

## Contenido de app/build.gradle.kts

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.example.myapp"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.example.myapp"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = "11"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)

    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}
```

## Contenido de gradle/libs.versions.toml

```toml
[versions]
agp = "8.5.0"
kotlin = "2.0.0"
coreKtx = "1.13.1"
lifecycleRuntimeKtx = "2.8.2"
activityCompose = "1.9.0"
composeBom = "2024.06.00"
junit = "4.13.2"
junitVersion = "1.2.1"
espressoCore = "3.6.1"

[libraries]
androidx-core-ktx = { group = "androidx.core", name = "core-ktx", version.ref = "coreKtx" }
androidx-lifecycle-runtime-ktx = { group = "androidx.lifecycle", name = "lifecycle-runtime-ktx", version.ref = "lifecycleRuntimeKtx" }
androidx-activity-compose = { group = "androidx.activity", name = "activity-compose", version.ref = "activityCompose" }
androidx-compose-bom = { group = "androidx.compose", name = "compose-bom", version.ref = "composeBom" }
androidx-ui = { group = "androidx.compose.ui", name = "ui" }
androidx-ui-graphics = { group = "androidx.compose.ui", name = "ui-graphics" }
androidx-ui-tooling = { group = "androidx.compose.ui", name = "ui-tooling" }
androidx-ui-tooling-preview = { group = "androidx.compose.ui", name = "ui-tooling-preview" }
androidx-ui-test-manifest = { group = "androidx.compose.ui", name = "ui-test-manifest" }
androidx-ui-test-junit4 = { group = "androidx.compose.ui", name = "ui-test-junit4" }
androidx-material3 = { group = "androidx.compose.material3", name = "material3" }
junit = { group = "junit", name = "junit", version.ref = "junit" }
androidx-junit = { group = "androidx.test.ext", name = "junit", version.ref = "junitVersion" }
androidx-espresso-core = { group = "androidx.test.espresso", name = "espresso-core", version.ref = "espressoCore" }

[plugins]
android-application = { id = "com.android.application", version.ref = "agp" }
kotlin-android = { id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }
kotlin-compose = { id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }
```

## Contenido mínimo de app/src/main/AndroidManifest.xml

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.MyApp">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:label="@string/app_name"
            android:theme="@style/Theme.MyApp">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

    </application>

</manifest>
```

## Estructura de carpetas

```
MyApp/
├── app/
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/example/myapp/
│   │   │   │   ├── MainActivity.kt
│   │   │   │   ├── ui/
│   │   │   │   │   ├── theme/
│   │   │   │   │   └── screens/
│   │   │   │   ├── viewmodel/
│   │   │   │   ├── data/
│   │   │   │   │   ├── repository/
│   │   │   │   │   └── model/
│   │   │   │   └── di/
│   │   │   ├── res/
│   │   │   └── AndroidManifest.xml
│   │   ├── test/
│   │   └── androidTest/
│   └── build.gradle.kts
├── gradle/
│   ├── libs.versions.toml
│   └── wrapper/
│       └── gradle-wrapper.properties
├── build.gradle.kts
├── settings.gradle.kts
├── gradlew
├── gradlew.bat
├── local.properties         ← NUNCA commitear
└── .gitignore
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar Android Studio (https://developer.android.com/studio) — incluye el SDK de Android
2. Abrir el proyecto en Android Studio (File > Open)
3. Android Studio detecta `local.properties` automáticamente; si no existe, crearlo con `sdk.dir=/path/to/Android/Sdk`
4. Sincronizar Gradle (Android Studio lo hace automáticamente al abrir)
5. Conectar un dispositivo Android o crear un AVD (Android Virtual Device)
6. Correr con el botón Run (triángulo verde) o Shift+F10

## Build commands

| Acción | Comando |
|--------|---------|
| Sincronizar Gradle | `./gradlew --refresh-dependencies` |
| Build debug | `./gradlew assembleDebug` |
| Build release | `./gradlew assembleRelease` |
| Tests unitarios | `./gradlew test` |
| Tests instrumentados | `./gradlew connectedAndroidTest` |
| Instalar en dispositivo | `./gradlew installDebug` |
| Limpiar build | `./gradlew clean` |

## Reglas del auditor (checklist para código generado)

1. **`local.properties` en `.gitignore`** — contiene el path del SDK local; es específico de cada máquina y nunca debe commitearse
2. **`gradle/libs.versions.toml` presente** — el Version Catalog es obligatorio en AGP 8+; sin él las dependencias no se resuelven correctamente
3. **`android:exported` en todas las Activities** — desde Android 12, toda Activity con `intent-filter` debe declarar `android:exported="true"` o la app no instala
4. **`namespace` en `app/build.gradle.kts`** — reemplaza el atributo `package` en AndroidManifest desde AGP 7.3; sin él hay warning y posible error de build
5. **`buildFeatures { compose = true }`** — sin esto el compilador Kotlin no procesa `@Composable`
6. **Kotlin DSL (`.kts`)** — los archivos de build deben ser `.gradle.kts`, no `.gradle` (Groovy)
7. **`gradlew` y `gradlew.bat` incluidos** — el Gradle Wrapper permite construir sin Gradle instalado globalmente; deben estar en el repositorio

## Errores comunes de generación AI

- Usar Groovy DSL (`.gradle`) en lugar de Kotlin DSL (`.gradle.kts`) — inconsistente con proyectos modernos
- Omitir `gradle/libs.versions.toml` y poner versiones de dependencias inline — no funciona con AGP 8.x si el proyecto usa Version Catalog
- Olvidar `android:exported="true"` en MainActivity — la app no instala en Android 12+
- `local.properties` commiteado — el SDK path de otra máquina rompe el build de otros developers
- No incluir `gradlew`/`gradlew.bat` — el usuario necesita Gradle instalado globalmente
- `namespace` sin declarar en `app/build.gradle.kts` — AGP lanza warning o error
- Usar `@Preview` sin importar `debugImplementation(libs.androidx.ui.tooling)` — las previews de Compose no funcionan
- `applicationId` diferente al `namespace` — permitido pero confuso; deben coincidir para proyectos simples
