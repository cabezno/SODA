## Skill: Android (Kotlin + Gradle)

You are building an Android application using Kotlin and Jetpack Compose. Follow these conventions:

- Use Jetpack Compose for all UI — no XML layouts for new projects
- Follow MVVM architecture: `ViewModel` + `UiState` data class + `Repository`
- Use `StateFlow` / `collectAsStateWithLifecycle()` for reactive UI state
- Dependency injection with Hilt (`@HiltViewModel`, `@HiltAndroidApp`, `@Inject`)
- Navigation with `androidx.navigation:navigation-compose`
- Network with Retrofit + OkHttp; parsing with kotlinx-serialization or Gson
- All build scripts in Kotlin DSL (`.gradle.kts`), never Groovy DSL
- `local.properties` is machine-specific — never commitear; contiene `sdk.dir`
- `minSdk = 26`, `targetSdk = 34`, `compileSdk = 34` como valores recomendados
