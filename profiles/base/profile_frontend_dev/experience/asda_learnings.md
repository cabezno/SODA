# Learnings from asda
*2026-04-25*

## Pattern: Full-Stack Next.js with Prisma
Using Next.js for both frontend and backend (via API routes and server components) with Prisma as the ORM proved highly effective for this e-commerce project. It streamlines development, ensures type-safety from database to UI, and simplifies deployment into a single stack.

## Pattern: Composable UI with shadcn/ui
Leveraging shadcn/ui and Tailwind CSS was a successful pattern for implementing the specific 'dark, elegant' design requirement. It provides unstyled, accessible components that can be easily customized, avoiding the rigidity of pre-built libraries and accelerating the creation of a bespoke theme.

## Pattern: NextAuth.js for Session Management
Integrating NextAuth.js for handling user authentication was a strong choice. Its middleware is perfectly suited for protecting routes like the checkout page, and its abstraction over JWTs and session handling simplifies the implementation of secure customer accounts.

## Anti-pattern: Self-hosted Transactional Email
Using a generic library like Nodemailer for critical transactional emails (order confirmation, etc.) can be risky in production due to potential deliverability issues (e.g., emails landing in spam). For future e-commerce projects, a dedicated transactional email service (like Resend, SendGrid) should be preferred for reliability and scalability.

## Preference: Server-Centric Architecture
The architecture shows a clear preference for handling logic on the server. The choice of Next.js with server components, API routes for business logic, and Prisma for data access points to a design philosophy that minimizes client-side complexity.

## Preference: Monolithic Application Structure
The co-location of UI, API, database schema, and core logic within a single Next.js project indicates a preference for a monolithic or 'monorepo-style' full-stack application over a distributed system with separate frontend and backend services.

## Preference: Type-Safe Data Flow
The use of TypeScript across the stack, combined with Prisma's auto-generated client, demonstrates a strong preference for end-to-end type safety. This reduces runtime errors and improves developer experience when handling data from the database to the UI.

## Knowledge Suggestion
Best practices for implementing idempotent webhook handlers for payment gateways like MercadoPago. This ensures that order status updates are processed exactly once, even if the payment provider sends the same event notification multiple times due to network issues.
