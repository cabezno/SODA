# Visual Design Principles for UI

## The 5 Core Principles

### 1. Visual Hierarchy
Guide the eye with size, weight, color, and spacing.
- **Size**: largest element = most important. Scale down deliberately.
- **Weight**: bold for primary info, regular for secondary, light for metadata.
- **Color**: primary color → high-priority actions only. Muted tones for supporting content.
- **Spacing**: more whitespace around important elements increases their perceived weight.

**Test**: blur your design and check if the focal point is still obvious. If not, hierarchy is weak.

### 2. Alignment & Grid
- All elements align to a grid. Use 8px base unit for all spacing values.
- **8pt grid**: 4, 8, 12, 16, 24, 32, 48, 64, 96px. Never 5, 7, 11, or arbitrary values.
- Left-align text blocks (not centered, unless UI is fully centered/card-based).
- Consistent left edge for related content groups.

### 3. Proximity
- Elements that belong together are close to each other.
- Distance = separation. Group labels with their inputs. Group actions with their subject.
- Use `gap` in flex/grid to control spacing uniformly. Avoid inconsistent margins.

### 4. Repetition / Consistency
- Identical function → identical visual treatment, everywhere.
- One button style per semantic role (primary / secondary / destructive).
- Font sizes from the scale only. Colors from the token system only.
- Border radius consistent per component type (cards: 12px, inputs: 8px, badges: 999px).

### 5. Contrast
- Visual contrast = differentiation. Use it to distinguish:
  - Interactive vs. static elements.
  - Primary vs. secondary actions.
  - Active vs. inactive states.
  - Content hierarchy levels.

## Spacing System (8px Base Grid)

```
4px  — micro gap (icon + label, inline badge)
8px  — compact (tight lists, dense tables)
12px — small (input padding, chip spacing)
16px — base (card padding inner, form field gap)
24px — medium (section gap, card gap)
32px — large (between sections on page)
48px — xl (major section breaks)
64px — 2xl (hero sections, page-level padding)
96px — 3xl (landing page section gaps)
```

## Shadow Elevation System

```css
/* 3-level elevation — don't mix levels arbitrarily */
--shadow-1: 0 1px 3px 0 rgb(0 0 0 / 0.1),  0 1px 2px -1px rgb(0 0 0 / 0.1); /* cards, inputs */
--shadow-2: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1); /* dropdowns, popovers */
--shadow-3: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1); /* modals, drawers */
--shadow-4: 0 25px 50px -12px rgb(0 0 0 / 0.25); /* overlays, floating panels */
```

Level 1 = resting surface. Level 2 = interactive/focused. Level 3 = overlaid. Level 4 = modal.

## Border Radius Scale

```css
--radius-none: 0;
--radius-sm:   4px;   /* tags, chips, code blocks */
--radius-md:   8px;   /* inputs, buttons, small cards */
--radius-lg:   12px;  /* cards, panels */
--radius-xl:   16px;  /* large cards, modal */
--radius-2xl:  24px;  /* hero cards, feature blocks */
--radius-full: 9999px; /* badges, avatars, pills */
```

**Rule**: More rounded = more friendly/consumer. Less rounded = more professional/enterprise.

## Layout Composition Patterns

### F-Pattern (reading flow)
Users scan left-to-right, then down the left edge. Place:
- Logo / brand: top-left.
- Navigation: top horizontal or left vertical.
- Primary CTA: top-right or following content flow.
- Important metadata: left-aligned, above the fold.

### Z-Pattern (marketing pages)
Eyes move: top-left → top-right → diagonal → bottom-left → bottom-right.
- Hero image fills top.
- Value prop in diagonal path.
- CTA at bottom-right of the Z.

### Dashboard Layout
```
┌──────────────────────────────────────────────┐
│  Sidebar Nav (240px)  │  Top Bar              │
│                       │  ─────────────────────│
│  [Logo]               │  Breadcrumbs  [User]  │
│  Nav Item             │  ─────────────────────│
│  Nav Item             │  KPI  │ KPI │ KPI     │
│  ─ sub item           │  ─────────────────────│
│  Nav Item             │  Main Chart           │
│                       │  ─────────────────────│
│                       │  Table / Detail       │
└───────────────────────┴───────────────────────┘
```

## Interaction & Motion Principles

- **Transitions**: use `150ms` for micro (hover, focus). `250ms` for component enter/exit. `350ms` for page transitions.
- **Easing**: `ease-out` for elements entering (starts fast, slows). `ease-in` for elements leaving. `ease-in-out` for position changes.
- **Motion direction**: modals come from center-scale. Drawers slide from edge. Toasts drop from top or rise from bottom.
- **Reduce motion**: always respect `prefers-reduced-motion`. Disable or simplify animations.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Design Checklist (before shipping UI)

- [ ] All text passes WCAG AA contrast (4.5:1 body, 3:1 large)
- [ ] All interactive elements have visible focus ring
- [ ] Touch targets ≥ 44×44px on mobile
- [ ] Empty states designed for every list/table
- [ ] Loading states for every async operation
- [ ] Error states for every form and data fetch
- [ ] Dark mode tokens defined (if applicable)
- [ ] Consistent border-radius across same component type
- [ ] Spacing values all from 8px grid
- [ ] No magic numbers in CSS (use variables)
- [ ] Typography scale used consistently (no ad-hoc font sizes)
- [ ] Color palette used from token system only
