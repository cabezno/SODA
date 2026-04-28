## Skill: Java Spring Boot

You are building a Java Spring Boot application. Follow these conventions:

- Spring Boot 3.x with Java 17+; use `@SpringBootApplication` as entry point
- Layered architecture: `Controller → Service → Repository (JPA)`
- `@RestController` with `@RequestMapping`; return `ResponseEntity<T>` for full HTTP control
- Use `@Service`, `@Repository`, `@Component` stereotypes consistently
- JPA entities in `model/` or `entity/`; repositories extend `JpaRepository<T, ID>`
- DTOs for request/response — never expose JPA entities directly in API
- Bean Validation with `@Valid` and `javax.validation` annotations on DTOs
- `application.properties` or `application.yml` for config; use profiles for environments
- `pom.xml` with `spring-boot-starter-web`, `spring-boot-starter-data-jpa`, `spring-boot-starter-validation`
- Run with: `mvn spring-boot:run` or `./mvnw spring-boot:run`
