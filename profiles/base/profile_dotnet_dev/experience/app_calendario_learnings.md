# Learnings from app_calendario
*2026-04-22*

## Pattern: Modular Service-Oriented Backend
The architecture's separation of concerns into distinct modules (Auth, Users, Events, Notifications) is highly effective. It creates a clean, maintainable, and scalable backend where each part has a single responsibility, which is ideal for an application with intertwined but separate features like this one.

## Pattern: ORM-Driven Schema Management
Using Prisma to define the entire database schema in a single `schema.prisma` file provides a clear, version-controlled source of truth for the data model. This pattern simplifies migrations and ensures type-safe database access across the application, reducing runtime errors.

## Pattern: Stateless JWT Auth with Refresh Tokens
The strategy of using short-lived access tokens (15min) and long-lived refresh tokens (7 days) stored in httpOnly cookies is a secure and modern standard. It works perfectly for supporting both web and mobile clients from a single API without relying on server-side sessions.

## Anti-pattern: Profile-Stack Mismatch
The active profile is `profile_dotnet_dev`, yet the entire proposed architecture is Node.js/TypeScript. This is a critical misalignment that risks non-idiomatic code and future maintenance issues. The profile's core technology stack should be prioritized unless project constraints explicitly require another.

## Anti-pattern: Ignoring the Mobile Delivery Strategy
The user explicitly requested an 'Android APK', but the architecture only details the backend API. It completely omits the frontend and mobile build strategy (e.g., PWA, Capacitor, React Native), leaving a core platform requirement unaddressed in the technical plan.

## Preference: API-First Decoupled Architecture
The design focuses entirely on creating a backend API, implying a clear preference for a decoupled system where multiple clients (web, mobile) can consume the same services. This is a modern approach that enhances flexibility.

## Preference: Leveraging External Identity Providers
The decision to use Google OAuth exclusively for authentication shows a preference for offloading user management and security. This simplifies the application by removing the need to build and maintain complex features like password storage, email verification, and password resets.

## Preference: Type-Safety Over Dynamic Typing
The choice of TypeScript and Prisma (a type-safe ORM) over plain JavaScript and raw SQL indicates a strong preference for a development environment that catches errors at compile-time, improving code quality and long-term maintainability.

## Knowledge Suggestion
CapacitorJS: A tool for packaging a web application into a native Android (APK) and iOS binary. This knowledge would directly bridge the gap between the proposed web-centric API architecture and the user's explicit requirement for a native mobile app, without needing to build a separate mobile codebase.
