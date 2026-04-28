# SODA BACKEND TEMPLATE: Go Microservice

## Estructura (Standard Go Layout):
- **cmd/:** Puntos de entrada de la aplicación.
- **internal/:** Código privado del servicio (negocio, datos).
- **pkg/:** Código que puede ser importado por otros proyectos.
- **api/:** Definiciones de contratos (Swagger/Proto).

## Stack:
- Gin Gonic (Framework web).
- GORM (ORM).
- Go 1.21+.
- Docker Multi-stage para imágenes de < 20MB.
