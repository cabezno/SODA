# Learnings from landing_page_prueba
*2026-04-28*

## Pattern: Modular Architecture for Landing Pages
Structuring a Next.js landing page into distinct modules (design_system, ui_shared, core_utils, static_data, and feature sections) worked well. This separation of concerns simplifies maintenance and makes it easy to manage a specific, custom aesthetic like the 'futuristic neon' theme.

## Pattern: Shared Validation Schema
Using a single Zod schema in a `core_utils` module for both client-side form validation (in React components) and server-side validation (in the API route) is a highly effective pattern. It eliminates code duplication and ensures data integrity consistently.

## Pattern: Static Data for Stable Content
For content that doesn't change often (services, testimonials), storing it in dedicated static files within the codebase is a pragmatic and fast approach. It avoids the overhead of a Headless CMS for a simple project like a landing page.

## Preference: Next.js for Integrated Backend
The choice of Next.js for a landing page indicates a preference for using its integrated API Routes to handle simple backend logic (like the contact form emailer) within the same project, avoiding the need for a separate server.

## Preference: Tailwind CSS for Theming
The presence of `tailwind.config.ts` and a `design_system` module points to a preference for utility-first CSS. This approach is particularly effective for implementing bespoke, theme-heavy designs with custom properties like neon glows and colors.

## Preference: Serverless Email Submission
The user's clarification to only send an email, combined with the `contact_api` module, implies a preference for using a serverless function (Next.js API Route) integrated with a third-party email service (like Resend or SendGrid) instead of setting up a database or a full backend.

## Knowledge Suggestion
How to implement email sending from Next.js API Routes using a service like Resend or Nodemailer, including environment variable management for API keys.
