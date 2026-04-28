## Skill: PostgreSQL

You are working with PostgreSQL. Follow these conventions:

- Connection string in environment variable (`DATABASE_URL`)
- Use migrations to manage schema — never alter tables manually
- Always define indexes on foreign keys and frequently filtered columns
- Use transactions for operations that modify multiple tables
- Prefer UUIDs as primary keys for distributed systems

**Node.js (Prisma):** Define schema in `prisma/schema.prisma`; use `prisma migrate dev`
**Go (GORM):** `AutoMigrate` in development; raw migrations in production
**Java (JPA):** Use `spring.jpa.hibernate.ddl-auto=validate` in production
**Python (SQLAlchemy):** Use Alembic for migrations; `alembic upgrade head`
