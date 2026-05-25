# Learnings from atento_claude
*2026-04-28*

## Pattern: Minimal Viable Backend (Single PHP Script)
For simple contact forms, avoiding a full backend framework (like Node.js) in favor of a single, isolated PHP script is highly effective. It directly meets the user's explicit requirement for simplicity, reduces hosting complexity, and is fast to implement, while still allowing for modern frontend interactions via AJAX.

## Pattern: Explicit 'No Persistence' Layer
Defining a 'capa_persistencia_nula' (Null Persistence Layer) in the architecture was a valuable pattern. It formally documents the user's decision to not store messages in a database, preventing scope creep and making the system's data-handling behavior unambiguous.

## Pattern: Decoupled Form Submission
Using asynchronous JavaScript (fetch/AJAX) to submit the form to the PHP endpoint worked well. This provides a smooth user experience without page reloads, cleanly separating the frontend (managed by this profile) from the minimal backend logic.

## Anti-pattern: Stretching a Frontend Profile for Backend Tasks
The project required a backend PHP script, which is outside the core competency of a 'profile_frontend_dev' with skills like Next.js and UI design. While it worked for this minimal case, it's an anti-pattern to assign backend tasks to a frontend-specialized profile, as it could fail if the backend logic becomes even slightly more complex.

## Preference: Pragmatism Over Architectural Purity
The user explicitly rejected a robust, full-stack solution (Node.js, DB) in favor of the simplest possible working implementation (a single PHP mailer script). This indicates a strong preference for minimizing complexity and infrastructure overhead over following a more conventional, but over-engineered, architectural pattern.

## Preference: Stateless Processing
The choice to send data directly to an email inbox and not store it in a database shows a preference for stateless backend logic. The server's role is purely transactional—receive, process, forward—which simplifies data privacy and server management.

## Preference: Prioritizing Visuals and UX
The user's first and most detailed clarifications were about the visual design (dark theme, vibrant colors) and user experience. This suggests a preference for projects where the primary focus is on a high-quality, modern user interface, with backend functionality being purely utilitarian.

## Knowledge Suggestion
Serverless functions for form handling (e.g., using Vercel/Netlify Functions with an email API like Resend) as a modern, secure alternative to self-hosted PHP scripts for JAMstack projects.
