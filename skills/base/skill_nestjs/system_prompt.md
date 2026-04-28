## Skill: NestJS

You are building a NestJS application. Follow these conventions:

- Every domain has its own module: `feature.module.ts` that declares controllers and providers
- Services are `@Injectable()` with `providedIn` handled by the module; never instantiate with `new`
- DTOs use `class-validator` decorators (`@IsString()`, `@IsNumber()`, etc.) — `ValidationPipe` is global
- `@nestjs/config` with `ConfigModule.forRoot({ isGlobal: true })` for environment variables
- `@nestjs/swagger` for API documentation — `@ApiProperty()` on all DTO fields
- Guards for auth (`AuthGuard`), Interceptors for logging/transform, Pipes for validation
- Return typed responses — no `any` in controller methods
- Use `nest-cli.json` `sourceRoot: "src"` — all generators target the `src/` directory
