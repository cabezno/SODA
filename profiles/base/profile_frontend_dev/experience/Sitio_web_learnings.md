# Learnings from Sitio_web
*2026-04-22*

## Pattern: CSS Variables for Theming
For a single-page site with a highly specific color palette, using CSS variables for colors (e.g., --amarillo, --celeste) was very effective. It centralized the theme definition, making it easy to apply the user's branding requirements consistently and simplifying future updates.

## Pattern: Semantic Sectioning for Single-Page Layouts
Structuring the landing page with semantic HTML tags (<section>, <nav>, <footer>) and corresponding IDs for anchor-based navigation created a clean, accessible, and SEO-friendly foundation. This pattern works perfectly with a sticky navigation bar for smooth intra-page scrolling.

## Pattern: Backend-less Forms with HTML5 Validation
For a static site, implementing a contact form with only native HTML5 validation and a static action (like `mailto:`) is a robust, lightweight pattern. It provides essential user feedback on input format without adding the complexity of JavaScript or server-side logic, fitting the project's scope perfectly.

## Preference: Preference for Vanilla Stack
The choice of plain HTML and CSS without any frameworks (like Bootstrap) or JS libraries for a static landing page reveals a preference for a minimal, dependency-free stack. This prioritizes performance, simplicity, and maintainability for small-scale projects.

## Preference: Design-Centric CSS Architecture
The CSS was structured to directly map the client's specific visual requests, especially the color palette via variables. This indicates a preference for a design-first approach where the visual identity dictates the CSS structure, making the theme the central part of the implementation.

## Preference: Separation of Structure and Content
Building the entire site with placeholder content ('texto de prueba') demonstrates a preferred workflow of decoupling the development of layout and styling from the final copywriting. This allows for a focus on creating a robust visual template first.

## Knowledge Suggestion
Static Site Form Handling with Third-Party Services (e.g., Netlify Forms, Formspree) to provide functional form submission without a dedicated backend, as a more robust alternative to `mailto:` links.
