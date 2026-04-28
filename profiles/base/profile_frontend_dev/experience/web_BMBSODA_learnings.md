# Learnings from web_BMBSODA
*2026-04-22*

## Pattern: Serverless Backend with API Routes
Using Next.js API Routes to handle form submissions and trigger server-side logic (like sending emails with Nodemailer) is highly effective for marketing sites. It avoids the complexity of a separate backend server, simplifying the tech stack and deployment while keeping the logic secure.

## Pattern: Decoupled Service Layer
Abstracting the email sending functionality into a dedicated service module (`lib/mailer.ts`) is a robust pattern. It isolates the Nodemailer dependency, keeps the API route logic clean and focused, and makes it easy to swap email providers in the future (e.g., to SendGrid or Resend).

## Pattern: Design System as Code via Tailwind Config
Defining the project's specific brand colors (cian, magenta, yellow) and other design tokens directly in `tailwind.config.ts` worked perfectly. It creates a single source of truth for the visual identity, ensuring consistency across all components and simplifying global style updates.

## Preference: Server-Side Logic for Core Actions
The choice of a server-side API Route over a client-side solution like EmailJS indicates a preference for security and control, keeping core actions like form processing off the client.

## Preference: Atomic and Reusable UI
The architecture's explicit creation of a `components/ui` directory for generic elements (Button, Card, Input) shows a strong preference for building interfaces from small, reusable, and composable components, which accelerates development and ensures consistency.

## Preference: Utility-First CSS
The selection of Tailwind CSS demonstrates a clear preference for a utility-first approach, enabling rapid implementation of a custom design by composing utilities directly in the markup.

## Knowledge Suggestion
Integrating dedicated transactional email APIs (e.g., Resend, SendGrid) into Next.js API Routes to improve email deliverability and tracking for production environments.
