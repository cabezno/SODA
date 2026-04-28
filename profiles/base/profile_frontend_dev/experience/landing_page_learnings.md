# Learnings from landing_page
*2026-04-27*

## Pattern: Serverless Form Handling via BaaS
Using a client-side service like EmailJS for the contact form was highly effective. It fulfilled the core requirement of sending an email without introducing the complexity and cost of a backend, making it a perfect pattern for static landing pages.

## Pattern: Modular Vanilla CSS Architecture
Separating CSS into dedicated files for tokens, base styles, layout, and components proved to be a clean and maintainable approach. This structure provides scalability and clarity even without a framework, making it easy to manage the 'futuristic' aesthetic.

## Pattern: Performance-first Animations
Employing the Intersection Observer API for scroll-reveal animations on the features section is a modern, performant choice. It avoids expensive scroll event listeners, ensuring a smooth experience that aligns with the 'elegant' and 'minimalist' design goal.

## Anti-pattern: Irrelevant Build Configuration
The inclusion of a `Cargo.toml` and Rust-related VS Code configuration was inappropriate for a pure HTML/CSS/JS project. Project scaffolding should be strictly limited to the tech stack in use to avoid confusion and unnecessary files.

## Preference: Vanilla-First Implementation
The choice to build the entire site with plain HTML, CSS, and JavaScript, without any frameworks, indicates a preference for lightweight, dependency-free solutions that offer maximum control and performance for single-page sites.

## Preference: Clear Separation of Concerns
The architecture distinctly separates structure (HTML), presentation (multiple CSS files), and behavior (JS). This classic but well-executed separation shows a preference for maintainability and clarity in the codebase.

## Preference: Aesthetic-driven Structure
The design choices, such as a sticky transparent header, Z-pattern layout, and glowing card borders, show a strong preference for letting the desired aesthetic (futuristic, elegant) directly inform the technical implementation and structure.

## Knowledge Suggestion
Integration patterns for EmailJS: How to securely implement the client-side SDK for form submission, including handling API keys and managing user-facing loading, success, and error states.
