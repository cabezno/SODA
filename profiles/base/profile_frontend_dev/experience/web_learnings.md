# Learnings from web
*2026-04-23*

## Pattern: Decoupling Content from UI
Separating all static text (hero, features, FAQs, prices) into a central `lib/data/content.ts` file proved highly effective. This pattern simplifies content updates for non-developers, streamlines the process for future CMS integration or i18n, and keeps UI components clean and focused on logic and structure.

## Pattern: Unified Type-Safe Validation
Defining a single Zod schema (`lib/validations/contactSchema.ts`) and using it for both client-side validation (React Hook Form) and server-side validation (Next.js API Route) worked extremely well. This ensures data consistency, prevents invalid submissions, and provides end-to-end type safety with a single source of truth.

## Pattern: SEO as a Core Architectural Module
Treating SEO as a first-class citizen by creating a dedicated architecture module for `sitemap.ts`, `robots.ts`, and metadata generation is a strong pattern for landing pages. This ensures the project is production-ready and aligned with business goals of discoverability from the start, rather than being an afterthought.

## Anti-pattern: Inconsistent Project Scaffolding
The architecture included a module (`infraestructura_build`) with configuration files for an unrelated tech stack (Rust's `Cargo.toml`). This creates confusion, adds unnecessary files to the project, and indicates a lack of proper cleanup from a boilerplate or template, which can mislead future developers.

## Preference: Serverless Functions for Backend Logic
The choice to use Next.js API Routes with the Resend SDK for the contact form shows a clear preference for a lightweight, serverless approach. This avoids the overhead of a dedicated backend server for simple, isolated tasks, which is highly efficient for landing pages and small-scale applications.

## Preference: Component-Driven UI with Utility-First Styling
The stack (Next.js, TailwindCSS, shadcn/ui) reveals a preference for building UIs with unstyled, accessible component primitives that are then styled using utility classes. This offers maximum design flexibility while maintaining code structure and reusability.

## Preference: Scoped State Management
The explicit decision to use a local `useState` hook for the monthly/annual pricing toggle, rather than a global state manager, demonstrates a preference for keeping state management as simple and locally scoped as possible, preventing premature complexity.

## Knowledge Suggestion
Advanced Pattern: Implementing end-to-end type-safe forms in Next.js using a shared Zod schema for React Hook Form (client) and API Routes (server).
