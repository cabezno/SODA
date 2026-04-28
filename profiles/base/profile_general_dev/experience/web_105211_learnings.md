# Learnings from web_105211
*2026-04-21*

## Pattern: Minimalist Structure for Static Sites
For projects requiring only HTML and CSS, a flat structure with `index.html` at the root and a dedicated `css/` directory for stylesheets is highly effective. It maintains a clean separation of concerns without introducing unnecessary complexity, making the project easy to navigate and deploy.

## Pattern: Zero-Dependency Development
Leveraging plain HTML and CSS without any pre-processors or build tools is a powerful pattern for simple landing pages. This approach eliminates dependencies, simplifies the development workflow to 'edit and refresh', and makes deployment trivial (e.g., drag-and-drop to a host).

## Preference: Strict Separation of Concerns
The design shows a strong preference for separating structure (HTML) from presentation (CSS) by using an external stylesheet, even for a single-page project. This indicates a bias towards maintainable and scalable code from the outset.

## Preference: Conventional Naming
The use of standard file names like `index.html` and `style.css` demonstrates a preference for convention and clarity over project-specific naming. This makes the project instantly understandable to any developer without context.

## Knowledge Suggestion
Deep dive into modern CSS layout techniques like Flexbox and Grid. Understanding their specific use cases (Flexbox for 1D alignment of components, Grid for 2D page layouts) allows for creating complex responsive designs with more semantic and maintainable code than traditional methods.
