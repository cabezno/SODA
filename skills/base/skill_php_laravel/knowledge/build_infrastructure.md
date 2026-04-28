# Build Infrastructure Checklist — PHP Laravel

## Archivos que SIEMPRE deben generarse

| Archivo | Por qué es obligatorio |
|---------|----------------------|
| `composer.json` | Sin esto Composer no puede instalar el framework ni sus dependencias |
| `composer.lock` | Debe commitearse; garantiza versiones exactas de dependencias |
| `.env.example` | Laravel busca este archivo como plantilla; sin él `php artisan key:generate` no sabe qué generar |
| `.env` | Variables reales de la aplicación; nunca commitear |
| `artisan` | CLI de Laravel — sin este archivo ningún comando `php artisan` funciona |
| `bootstrap/app.php` | Sin él la aplicación Laravel no puede bootstrapear |
| `public/index.php` | Entry point del servidor web; sin él Apache/Nginx no sabe dónde apuntar |
| `config/app.php` | Configuración base (timezone, locale, providers) |
| `.gitignore` | Debe excluir `vendor/`, `.env`, `storage/`, `bootstrap/cache/` |
| `README.md` | Sin instrucciones el usuario no sabe cómo correr el proyecto |
| `.vscode/tasks.json` | Sin esto Ctrl+Shift+B no lanza el servidor |
| `.vscode/launch.json` | Sin esto F5 no inicia el debugger PHP (Xdebug) |
| `.vscode/extensions.json` | Recomienda PHP Intelephense, Laravel Extension Pack |

## Contenido mínimo de composer.json

```json
{
    "name": "myorg/myapp",
    "type": "project",
    "description": "Laravel application",
    "require": {
        "php": "^8.2",
        "laravel/framework": "^11.0",
        "laravel/tinker": "^2.9"
    },
    "require-dev": {
        "fakerphp/faker": "^1.23",
        "laravel/pint": "^1.13",
        "laravel/sail": "^1.26",
        "mockery/mockery": "^1.6",
        "nunomaduro/collision": "^8.0",
        "phpunit/phpunit": "^11.0"
    },
    "autoload": {
        "psr-4": {
            "App\\": "app/",
            "Database\\Factories\\": "database/factories/",
            "Database\\Seeders\\": "database/seeders/"
        }
    },
    "autoload-dev": {
        "psr-4": {
            "Tests\\": "tests/"
        }
    },
    "scripts": {
        "post-autoload-dump": [
            "Illuminate\\Foundation\\ComposerScripts::postAutoloadDump",
            "@php artisan package:discover --ansi"
        ],
        "post-update-cmd": [
            "@php artisan vendor:publish --tag=laravel-assets --ansi --force"
        ],
        "post-root-package-install": [
            "@php -r \"file_exists('.env') || copy('.env.example', '.env');\""
        ],
        "post-create-project-cmd": [
            "@php artisan key:generate --ansi"
        ]
    },
    "minimum-stability": "stable",
    "prefer-stable": true
}
```

## Contenido mínimo de .env.example

```
APP_NAME=MyApp
APP_ENV=local
APP_KEY=
APP_DEBUG=true
APP_URL=http://localhost:8000

LOG_CHANNEL=stack
LOG_LEVEL=debug

DB_CONNECTION=sqlite
DB_DATABASE=/absolute/path/to/database.sqlite

BROADCAST_DRIVER=log
CACHE_DRIVER=file
FILESYSTEM_DISK=local
QUEUE_CONNECTION=sync
SESSION_DRIVER=file
SESSION_LIFETIME=120

MAIL_MAILER=log
```

## Estructura de carpetas obligatoria (Laravel 11)

```
myapp/
├── app/
│   ├── Http/
│   │   ├── Controllers/
│   │   └── Middleware/
│   ├── Models/
│   └── Providers/
├── bootstrap/
│   ├── app.php              ← entry point del framework
│   └── providers.php
├── config/
├── database/
│   ├── migrations/
│   ├── factories/
│   └── seeders/
├── public/
│   └── index.php            ← entry point del web server
├── resources/
│   └── views/
├── routes/
│   ├── api.php
│   ├── web.php
│   └── console.php
├── storage/
├── tests/
├── vendor/                  ← generado por composer, NO commitear
├── artisan
├── composer.json
├── composer.lock
├── .env.example
└── .gitignore
```

## .vscode/tasks.json

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Composer install",
      "type": "shell",
      "command": "composer install",
      "group": "build"
    },
    {
      "label": "Laravel: Serve",
      "type": "shell",
      "command": "php artisan serve",
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "dedicated" }
    },
    {
      "label": "Laravel: Migrate",
      "type": "shell",
      "command": "php artisan migrate",
      "group": "build"
    },
    {
      "label": "Laravel: Test",
      "type": "shell",
      "command": "php artisan test",
      "group": { "kind": "test", "isDefault": true }
    }
  ]
}
```

## .vscode/launch.json (requiere Xdebug instalado)

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "PHP: Listen for Xdebug",
      "type": "php",
      "request": "launch",
      "port": 9003,
      "pathMappings": {
        "${workspaceFolder}": "${workspaceFolder}"
      }
    },
    {
      "name": "PHP: Launch artisan serve",
      "type": "php",
      "request": "launch",
      "program": "${workspaceFolder}/artisan",
      "args": ["serve"],
      "cwd": "${workspaceFolder}",
      "port": 9003
    }
  ]
}
```

## .vscode/extensions.json

```json
{
  "recommendations": [
    "bmewburn.vscode-intelephense-client",
    "onecentlin.laravel-extension-pack",
    "amirmarmul.laravel-blade-vscode",
    "humao.rest-client",
    "mikestead.dotenv"
  ]
}
```

## Pasos que debe ejecutar el usuario para correr el proyecto

1. Instalar PHP >= 8.2 con extensiones: `openssl`, `pdo`, `mbstring`, `tokenizer`, `xml`, `ctype`, `json`, `bcmath`
2. Instalar Composer (https://getcomposer.org/)
3. Instalar dependencias: `composer install`
4. Copiar `.env.example` a `.env`: `cp .env.example .env`
5. Generar clave de la app: `php artisan key:generate`
6. Ejecutar migraciones: `php artisan migrate`
7. Correr servidor: `php artisan serve`
8. Abrir http://localhost:8000

## Build commands

| Acción | Comando |
|--------|---------|
| Instalar deps | `composer install` |
| Dev server | `php artisan serve` |
| Migraciones | `php artisan migrate` |
| Seed de datos | `php artisan db:seed` |
| Limpiar caché | `php artisan optimize:clear` |
| Tests | `php artisan test` |
| Tests PHPUnit | `./vendor/bin/phpunit` |
| Linting | `./vendor/bin/pint` |
| Producción | `composer install --no-dev && php artisan optimize` |

## Reglas del auditor (checklist para código generado)

1. **`APP_KEY` generada** — debe haber instrucción explícita de `php artisan key:generate`; sin APP_KEY la app lanza `RuntimeException` al arrancar
2. **Rutas en `routes/api.php` o `routes/web.php`** — nunca definir rutas en controladores o en `app.php`; en Laravel 11 `api.php` no se carga por defecto si no se registra en `bootstrap/app.php`
3. **Migraciones para cada tabla** — todo modelo Eloquent con base de datos necesita su archivo en `database/migrations/`; sin ellas `php artisan migrate` no crea las tablas
4. **`$fillable` o `$guarded` en modelos Eloquent** — sin `$fillable`, la asignación masiva lanza `MassAssignmentException`
5. **`vendor/` en `.gitignore`** — la carpeta de dependencias nunca debe commitearse
6. **`composer.lock` commiteado** — garantiza versiones exactas; no ponerlo en `.gitignore`
7. **Policies/Gates para autorización** — no hacer chequeos de permisos en controllers directamente; usar `$this->authorize()` o `Gate::allows()`
8. **`storage/` y `bootstrap/cache/` con permisos de escritura** — el README debe indicar `chmod -R 775 storage bootstrap/cache`

## Errores comunes de generación AI

- Olvidar `php artisan key:generate` en las instrucciones de setup — la app no arranca sin `APP_KEY`
- No registrar la ruta API en `bootstrap/app.php` (Laravel 11) — `routes/api.php` no se carga automáticamente en la versión actual
- Olvidar `$fillable` en modelos — cualquier `Model::create()` lanza excepción
- No incluir `composer.lock` — el build en CI puede usar versiones diferentes
- No separar autenticación/autorización con Policies — lógica de permisos hardcodeada en controllers
- Rutas no nombradas — sin `->name('route.name')` las rutas no se pueden referenciar con `route()`
- Olvidar `php artisan migrate` en las instrucciones — la base de datos no tiene tablas
- No generar el directorio `storage/app/public` con `php artisan storage:link` cuando se usan uploads
