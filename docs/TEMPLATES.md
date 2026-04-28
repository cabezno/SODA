# SODA Blueprint System

Este documento detalla las plantillas (blueprints) disponibles en SODA y sus especificaciones técnicas.

## 1. Fullstack: FastAPI + React (`templates/fullstack/fastapi-react`)
Estructura de referencia para aplicaciones web modernas que requieren alta performance y tipado fuerte en ambos extremos.

- **Backend:** FastAPI, SQLModel, PostgreSQL.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS.
- **DevOps:** Docker Compose con Traefik como Reverse Proxy.
- **Patrón:** Separación clara entre `backend/` y `frontend/`.

## 2. Backend: Node.js Clean Architecture (`templates/backend/node-clean-ts`)
Diseñada para microservicios y APIs robustas donde la lógica de negocio debe estar aislada de los detalles técnicos.

- **Arquitectura:** Clean Architecture (Domain, Application, Infrastructure, Interfaces).
- **Runtime:** Node.js + TypeScript (compilado con tsup).
- **Framework:** Fastify para máxima velocidad.
- **ORM:** Prisma para acceso a datos seguro.

## 3. Mobile: React Native Expo (`templates/mobile/react-native-expo`)
Base multiplataforma para el desarrollo de apps móviles con una sola base de código.

- **Framework:** Expo Router (basado en archivos).
- **Estilos:** NativeWind (Tailwind CSS para móvil).
- **Runtime:** React Native con soporte para iOS, Android y Web.

## 4. Backend: Go Microservice (`templates/backend/go-microservice`)
Ideal para sistemas de alta concurrencia, procesamiento en tiempo real o microservicios que requieren el mínimo consumo de recursos.

- **Arquitectura:** Standard Go Project Layout.
- **Framework:** Gin Gonic.
- **Performance:** Compilación estática (Docker imágenes < 20MB).
- **Database:** Soporte nativo para PostgreSQL vía GORM.

## 5. Frontend: Next.js SEO Master (`templates/frontend/nextjs-seo`)
La opción definitiva para aplicaciones web públicas (E-commerce, Blogs, SaaS) que dependen del tráfico orgánico y la velocidad percibida.

- **Framework:** Next.js 14+ (App Router).
- **SEO:** Metadata API integrada, OpenGraph, Robots y Sitemaps automáticos.
- **UI:** Tailwind CSS + Radix UI.
- **Rendering:** Server-Side Rendering (SSR) y Static Site Generation (SSG).

---

## Cómo agregar una nueva plantilla
1. Crear la carpeta correspondiente en `/templates/<categoria>/<nombre>`.
2. Incluir un `README.md` con las especificaciones.
3. Asegurarse de incluir los archivos de configuración base (`Dockerfile`, `package.json`, `pyproject.toml`, etc.).
4. (Opcional) Agregar etiquetas `# --- METADATA SODA ---` en archivos clave para guiar a la IA.
