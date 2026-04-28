# SODA BACKEND TEMPLATE: Node.js Clean Architecture (TS)

## Estructura:
- **Domain:** Entidades de negocio y reglas puras (sin dependencias externas).
- **Application:** Casos de uso y orquestación.
- **Infrastructure:** Implementaciones técnicas (DB, Repositorios, APIs externas).
- **Interfaces:** Controladores, Routers y validadores de entrada.

## Stack:
- Fastify (más rápido que Express) o Express.
- TypeScript + Zod (validación).
- Prisma (ORM).
