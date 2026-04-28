# Learnings from proyecto_2
*2026-04-21*

## Pattern: Arquitectura Modular por Features
Organizar el backend en módulos por funcionalidad (Cuentas, Eventos, Notificaciones) con una base 'Core' para configuración y DB funcionó bien. Facilita la escalabilidad y el mantenimiento al aislar responsabilidades y gestionar dependencias de forma clara (e.g., inyectar la sesión de BD desde el Core).

## Pattern: Modelos de Datos Centralizados
Tener un único módulo 'Modelos' que define todas las tablas y relaciones con SQLAlchemy ORM es un patrón robusto. Crea una fuente única de verdad para la estructura de la base de datos, evitando dependencias circulares y simplificando la evolución del esquema.

## Pattern: Autenticación JWT con Refresh Tokens
El uso de tokens de acceso de corta duración (15 min) y tokens de refresco de larga duración (7 días) es una práctica de seguridad excelente para este tipo de aplicación. Ofrece un buen equilibrio entre seguridad y experiencia de usuario, evitando que el usuario inicie sesión constantemente.

## Anti-pattern: Notificaciones Basadas en Polling
Para una aplicación de eventos y social, depender de notificaciones in-app que requieran polling por parte del cliente es ineficiente. Genera carga innecesaria en el servidor y una experiencia de usuario con retrasos. Se debe evitar en favor de soluciones en tiempo real como WebSockets.

## Preference: Preferencia por Arquitectura en Capas (CRUD/Schemas/Routers)
La estructura interna de los módulos (e.g., 'Módulo Cuentas') dividida en `crud`, `schemas`, y `routers` revela una clara preferencia por la arquitectura en capas. Esto promueve una fuerte separación de responsabilidades: API, validación de datos y lógica de acceso a la base de datos.

## Preference: Uso de Inyección de Dependencias
El diseño se apoya en la inyección de dependencias de FastAPI (e.g., para la sesión de BD y el usuario autenticado). Esto indica una preferencia por un código desacoplado, explícito y más fácil de testear, evitando estados globales o importaciones implícitas.

## Preference: Esquema de Base de Datos Relacional (SQL)
La elección de SQLAlchemy y la definición de relaciones explícitas (User, Event, Invitation, Friendship) muestra una preferencia por un modelo de datos relacional y estructurado, adecuado para manejar las complejas interconexiones de una aplicación social como esta.

## Knowledge Suggestion
Integración de WebSockets en FastAPI para la gestión de notificaciones y actualizaciones de estado en tiempo real. Esto permitiría enviar invitaciones, confirmaciones de asistencia y otros eventos al cliente instantáneamente.
