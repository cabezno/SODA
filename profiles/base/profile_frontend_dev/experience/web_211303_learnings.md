# Learnings from web_211303
*2026-04-23*

## Pattern: Robust Form Handling with a BFF Pattern
Using React Hook Form + Zod for client-side validation, coupled with a Next.js API Route for server-side validation and email dispatch (via Nodemailer), is a highly effective and secure pattern for static sites. It provides a 'Backend-for-Frontend' without requiring a separate server.

## Pattern: Modular Architecture for Simple Sites
Even for a small informational site, separating concerns into modules (Core for types/schemas, UI, Email Service, API) creates a clean, maintainable, and scalable Next.js project. This prevents code from becoming monolithic.

## Pattern: Component-Driven UI with Tailwind
Establishing a base UI component library (`components/ui`) from the start, utilizing Tailwind CSS, is an efficient way to build a consistent and responsive design system that accelerates the development of informational pages.

## Preference: Schema-Driven Development
There is a strong preference for defining data contracts upfront using TypeScript interfaces and Zod schemas. This ensures type safety and validation consistency across the client and server.

## Preference: Serverless Functions for Backend Logic
The default approach for backend tasks is to leverage co-located serverless functions (Next.js API Routes) rather than a dedicated server, indicating a preference for a unified Jamstack architecture.

## Preference: Emphasis on Animations and UX
The explicit inclusion of Framer Motion in the blueprint for entry animations shows a preference for building visually engaging user experiences, even for a simple informational site.

## Knowledge Suggestion
Integrating a headless CMS (e.g., Sanity, Strapi) to manage form submissions. This would provide a persistent database for contacts beyond an email inbox and is a common next step for such projects.
