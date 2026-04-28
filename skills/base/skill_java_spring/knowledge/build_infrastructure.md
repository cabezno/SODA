# Build Infrastructure Checklist — Java Spring Boot

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `pom.xml` (Maven) O `build.gradle` + `settings.gradle` (Gradle) | Sin el descriptor de build, el proyecto no compila ni resuelve dependencias |
| `src/main/resources/application.properties` O `application.yml` | Sin esto Spring Boot no puede configurar el servidor ni la base de datos |
| `src/main/resources/application-dev.properties` | Perfil de desarrollo separado para no contaminar producción |
| `src/main/java/.../Application.java` | Clase con `@SpringBootApplication` y `main()` — entry point obligatorio |
| `.env.example` O `application-secrets.properties.example` | Documenta qué secretos configurar fuera del repositorio |
| `.gitignore` | Debe excluir `target/`, `build/`, `.env`, `*.class`, `*.jar` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no compila |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger Java |
| `.vscode/extensions.json` | Recomienda Extension Pack for Java, Spring Boot Extension Pack |

## Estructura de paquetes obligatoria (Maven)

```
src/
├── main/
│   ├── java/com/example/myapp/
│   │   ├── MyAppApplication.java     ← @SpringBootApplication
│   │   ├── controller/
│   │   ├── service/
│   │   ├── repository/
│   │   ├── model/  (o entity/)
│   │   └── dto/
│   └── resources/
│       ├── application.yml
│       └── application-dev.yml
└── test/
    └── java/com/example/myapp/
        └── MyAppApplicationTests.java
```

## Contenido mínimo de pom.xml

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.3.0</version>
    <relativePath/>
  </parent>

  <groupId>com.example</groupId>
  <artifactId>myapp</artifactId>
  <version>0.0.1-SNAPSHOT</version>
  <name>myapp</name>

  <properties>
    <java.version>21</java.version>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
```

## Contenido mínimo de application.yml

```yaml
server:
  port: 8080

spring:
  application:
    name: myapp
  profiles:
    active: dev

---
spring:
  config:
    activate:
      on-profile: dev
  datasource:
    url: jdbc:h2:mem:testdb
    driver-class-name: org.h2.Driver
  h2:
    console:
      enabled: true
```

## Alternativa: build.gradle (Gradle Kotlin DSL)

```kotlin
plugins {
    id("org.springframework.boot") version "3.3.0"
    id("io.spring.dependency-management") version "1.1.5"
    kotlin("jvm") version "1.9.24"
    kotlin("plugin.spring") version "1.9.24"
}

group = "com.example"
version = "0.0.1-SNAPSHOT"

java { sourceCompatibility = JavaVersion.VERSION_21 }

dependencies {
    implementation("org.springframework.boot:spring-boot-starter-web")
    implementation("org.springframework.boot:spring-boot-starter-validation")
    testImplementation("org.springframework.boot:spring-boot-starter-test")
}

tasks.withType<Test> { useJUnitPlatform() }
```

## settings.gradle (cuando se usa Gradle)

```groovy
rootProject.name = 'myapp'
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Maven: Build",
      "type": "shell",
      "command": "./mvnw clean package -DskipTests",
      "group": { "kind": "build", "isDefault": true },
      "problemMatcher": []
    },
    {
      "label": "Maven: Run",
      "type": "shell",
      "command": "./mvnw spring-boot:run",
      "group": "build",
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Maven: Test",
      "type": "shell",
      "command": "./mvnw test",
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
      "type": "java",
      "name": "Spring Boot: Run",
      "request": "launch",
      "mainClass": "com.example.myapp.MyAppApplication",
      "projectName": "myapp",
      "args": "",
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "vscjava.vscode-java-pack",
    "vmware.vscode-spring-boot",
    "vscjava.vscode-spring-initializr",
    "vscjava.vscode-spring-boot-dashboard",
    "humao.rest-client"
  ]
}
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar JDK >= 21 (https://adoptium.net/)
2. El proyecto incluye Maven Wrapper (`mvnw`) — no requiere Maven instalado globalmente
3. Copiar `application-secrets.properties.example` y completar valores reales
4. Correr: `./mvnw spring-boot:run` (Linux/Mac) o `mvnw.cmd spring-boot:run` (Windows)
5. Acceder a http://localhost:8080

## Build commands

| Acción | Comando |
|--------|---------|
| Compilar | `./mvnw compile` |
| Build + jar | `./mvnw clean package` |
| Dev server | `./mvnw spring-boot:run` |
| Tests | `./mvnw test` |
| Producción | `java -jar target/myapp-0.0.1-SNAPSHOT.jar` |
| Gradle build | `./gradlew build` |
| Gradle dev | `./gradlew bootRun` |

## Reglas del auditor (checklist para código generado)

1. **Clase `@SpringBootApplication` en paquete base** — la clase principal debe estar en el paquete raíz (e.g., `com.example.myapp`), no en un subpaquete; de lo contrario Spring no escanea los beans hijos
2. **Maven Wrapper incluido** — `mvnw`, `mvnw.cmd` y `.mvn/wrapper/maven-wrapper.properties` deben estar presentes; nunca depender de Maven global del usuario
3. **Perfiles de Spring configurados** — `application.yml` y `application-dev.yml` separados; nunca credenciales hardcodeadas en el archivo principal
4. **`@Repository`, `@Service`, `@RestController` correctos** — no usar `@Component` genérico cuando existe la anotación semántica; facilita el escaneo y claridad
5. **`spring-boot-starter-validation` incluido para DTOs** — si hay `@Valid` o `@NotNull` en DTOs, la dependencia de validación debe estar en `pom.xml`
6. **`@RequestBody` y `ResponseEntity<T>` en controllers** — los métodos deben declarar tipos de retorno específicos, no `Object` o `Map`
7. **Tests con `@SpringBootTest`** — al menos un test de integración que levante el contexto completo

## Errores comunes de generación AI

- Poner la clase `@SpringBootApplication` en un subpaquete (como `controller/`) — Spring no puede escanear el paquete raíz
- Omitir el Maven Wrapper — el usuario necesita tener Maven instalado globalmente o el comando `mvnw` falla
- Usar `@Autowired` en campos en lugar de inyección por constructor — rompe testabilidad y es anti-patrón moderno
- No incluir `spring-boot-starter-validation` pero usar anotaciones `@Valid`, `@NotBlank`, etc.
- Hardcodear `spring.datasource.password` en `application.yml` en lugar de usar variables de entorno
- Olvidar `@Entity`, `@Id`, `@GeneratedValue` en clases de entidad JPA
- No generar el archivo `settings.gradle` cuando se usa Gradle — el build falla sin él
- Usar Java 8 syntax (no `var`, no records) cuando el proyecto declara `java.version=21`
