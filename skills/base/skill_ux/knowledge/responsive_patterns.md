# Responsive Design Patterns

## Breakpoint System
Use these standard breakpoints consistently:
- **xs**: 0–479px (small phones)
- **sm**: 480–767px (large phones)
- **md**: 768–1023px (tablets)
- **lg**: 1024–1279px (small desktops / landscape tablets)
- **xl**: 1280–1535px (desktops)
- **2xl**: 1536px+ (large desktops)

## Layout Adaptation Patterns

### Navigation
| Desktop | Tablet | Mobile |
|---------|--------|--------|
| Horizontal top nav | Top nav with hamburger | Bottom nav bar |
| Sidebar visible | Sidebar collapsed (icon-only) | Sidebar hidden (drawer) |
| Full labels | Icon + tooltip | Icon only or bottom nav |

### Content Grid
- Desktop: 12-column grid, cards 3–4 per row.
- Tablet: 2 cards per row.
- Mobile: 1 card per row (full width).
- Always: `gap` consistent with spacing system (16px or 24px).

### Typography Scaling
```
          Mobile   Tablet   Desktop
h1        28px     36px     48px
h2        22px     28px     36px
h3        18px     22px     28px
body      15px     16px     16px
small     13px     14px     14px
```
Use `clamp()` for fluid scaling: `clamp(28px, 4vw, 48px)`.

### Forms
- Desktop: 2-column for related fields, max-width 640px centered.
- Tablet: 2-column or 1-column depending on complexity.
- Mobile: always 1-column, full-width inputs, stacked labels.
- Buttons: full-width on mobile, auto-width on desktop.

### Tables
- Desktop: full table with all columns visible.
- Tablet: hide 1–2 least-important columns, horizontal scroll as fallback.
- Mobile: card view (each row becomes a card) or horizontal scroll with sticky first column.
  ```
  /* Card view transformation */
  @media (max-width: 767px) {
    tr { display: block; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 12px; }
    td { display: flex; justify-content: space-between; }
    td::before { content: attr(data-label); font-weight: 600; }
  }
  ```

### Images & Media
- Always use `max-width: 100%` on images.
- Hero images: `object-fit: cover`, fixed height on desktop, aspect-ratio on mobile.
- `srcset` for multiple resolutions. `loading="lazy"` for below-fold images.
- Video: `width: 100%; aspect-ratio: 16/9`.

## CSS Best Practices for Responsive

### Container Queries (modern approach)
```css
.card-container { container-type: inline-size; }
@container (min-width: 400px) { .card { flex-direction: row; } }
```

### Fluid Spacing
```css
:root {
  --space-xs: clamp(4px, 1vw, 8px);
  --space-sm: clamp(8px, 2vw, 16px);
  --space-md: clamp(16px, 3vw, 24px);
  --space-lg: clamp(24px, 4vw, 48px);
}
```

### Touch vs Pointer
```css
@media (hover: hover) { .btn:hover { background: var(--btn-hover); } }
@media (pointer: coarse) { .btn { min-height: 44px; min-width: 44px; } }
```

## Component-Specific Responsive Rules

### Modals
- Desktop: centered overlay, max-width 560px.
- Tablet: centered, 90% width.
- Mobile: bottom sheet (slides up from bottom, full width).

### Sidebar Navigation
- Desktop: fixed sidebar 240–280px wide.
- Tablet: icon-only sidebar 64px (expand on hover/click).
- Mobile: hidden, opens as full-height overlay drawer from left.

### Data Tables on Mobile
Options in order of preference:
1. Card/list view transformation (best UX).
2. Horizontal scroll with sticky first column.
3. Priority columns only (hide non-essential).

### Charts & Graphs
- Always set `width: 100%` on chart containers.
- Simplify on mobile: fewer data points, larger touch targets.
- Consider switching chart types: grouped bar → stacked bar on mobile.
