## Skill: PHP Laravel

You are building a Laravel application. Follow these conventions:

- Laravel 11 with PHP 8.2+
- Use Resource Controllers (`php artisan make:controller --resource`) for CRUD
- Eloquent ORM: one Model per database table, relationships defined in model methods
- Migrations in `database/migrations/` for every schema change
- Form Requests for validation (`php artisan make:request`)
- API resources (`php artisan make:resource`) to transform model data for JSON responses
- Routes in `routes/api.php` for API endpoints, `routes/web.php` for web
- Services in `app/Services/` for business logic — keep controllers thin
- `.env` for configuration; use `config()` helper, never `$_ENV` directly
- Run with: `php artisan serve`; install: `composer install`
