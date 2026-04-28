# Learnings from pr1
*2026-04-23*

## Pattern: Next.js + Shadcn/UI + Tailwind Stack for Landing Pages
This combination is highly effective for building modern, responsive, and aesthetically pleasing informational websites. Next.js provides excellent SEO and performance, Tailwind CSS allows for rapid and precise styling, and Shadcn/UI offers high-quality, accessible, and easily customizable components, accelerating development without sacrificing control.

## Pattern: Type-Safe Forms with RHF and Zod
Using React Hook Form for performance and Zod for schema-based validation is a best-practice pattern for handling user input. It ensures data integrity from the client to the server, improves developer experience with autocompletion, and reduces runtime errors, which is critical for the site's primary conversion point (the contact form).

## Pattern: Modular Architecture for Static Sites
Even for a relatively simple informational site, structuring the code into distinct modules (Core, UI, Layout, Sections) proved beneficial. It keeps the codebase clean, promotes reusability (e.g., UI components), and makes future maintenance or expansion straightforward.

## Preference: Component Ownership over Abstraction
The choice of Shadcn/UI, where components are copied into the project rather than installed as a dependency, shows a preference for full control and ownership over the UI code. This allows for deep customization without fighting a library's API or styles.

## Preference: Utility-First CSS
The adoption of Tailwind CSS indicates a strong preference for a utility-first approach to styling. This prioritizes co-locating styles with the markup, leading to faster development cycles and avoiding the mental overhead of managing separate CSS files or class naming conventions.

## Preference: Server-Side Logic within a Frontend Framework
Leveraging Next.js for both the static frontend and the API endpoint to handle form submission shows a preference for a full-stack, single-framework solution. This simplifies the deployment process and keeps the entire application logic within one cohesive codebase.

## Knowledge Suggestion
Implementing server-side email sending in Next.js using Resend and React Email for transactional forms.
