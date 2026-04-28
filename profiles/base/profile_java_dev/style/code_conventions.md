# Java Developer Code Conventions

- PascalCase for classes, camelCase for methods and variables, UPPER_SNAKE for constants
- DTOs separate from JPA entities; MapStruct or manual mapping
- Service layer is the only place with business logic — controllers are thin
- Use Lombok (`@Data`, `@Builder`, `@NoArgsConstructor`) to reduce boilerplate
- All custom exceptions extend `RuntimeException`; handled by `@ControllerAdvice`
- Unit tests with JUnit 5 and Mockito; integration tests with `@SpringBootTest`
