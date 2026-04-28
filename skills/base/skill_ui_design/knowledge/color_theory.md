# Color Theory for UI Design

## Color Roles (always define these 7)

| Role | Purpose | Example |
|------|---------|---------|
| `primary` | Brand, CTAs, active states | #3b82f6 (blue) |
| `primary-dark` | Hover on primary | #2563eb |
| `secondary` | Supporting actions, accents | #8b5cf6 (violet) |
| `success` | Confirmations, positive states | #22c55e |
| `warning` | Caution, non-blocking alerts | #f59e0b |
| `danger` | Errors, destructive actions | #ef4444 |
| `neutral` | Text, borders, backgrounds | Gray scale |

## Palette Generation Strategy

### From a single brand color
1. Use the brand color as `primary-500`.
2. Generate lighter shades (50→400) by increasing lightness 5–8% per step.
3. Generate darker shades (600→900) by decreasing lightness 5–8% per step.
4. Pick `secondary` from an adjacent or complementary hue (60° or 180° on color wheel).

### Proven palette combinations
```
Blue + Violet:   primary #3b82f6, secondary #8b5cf6  (SaaS default)
Teal + Amber:    primary #14b8a6, secondary #f59e0b  (Fresh / fintech)
Slate + Indigo:  primary #6366f1, secondary #64748b  (Developer tool)
Rose + Orange:   primary #f43f5e, secondary #f97316  (Consumer / social)
Green + Blue:    primary #10b981, secondary #3b82f6  (Health / eco)
```

## CSS Variable Token System

Always output this block in the root stylesheet:
```css
:root {
  /* Brand */
  --color-primary:        #3b82f6;
  --color-primary-dark:   #2563eb;
  --color-primary-light:  #93c5fd;
  --color-secondary:      #8b5cf6;
  --color-secondary-dark: #7c3aed;

  /* Semantic */
  --color-success:  #22c55e;
  --color-warning:  #f59e0b;
  --color-danger:   #ef4444;
  --color-info:     #06b6d4;

  /* Neutral surface */
  --color-bg:           #ffffff;
  --color-bg-secondary: #f8fafc;
  --color-bg-tertiary:  #f1f5f9;
  --color-border:       #e2e8f0;
  --color-border-focus: var(--color-primary);

  /* Text */
  --color-text:         #0f172a;
  --color-text-muted:   #64748b;
  --color-text-inverse: #ffffff;
  --color-text-link:    var(--color-primary);
}

/* Dark mode */
[data-theme="dark"],
.dark {
  --color-bg:           #0f172a;
  --color-bg-secondary: #1e293b;
  --color-bg-tertiary:  #334155;
  --color-border:       #334155;
  --color-text:         #f1f5f9;
  --color-text-muted:   #94a3b8;
}
```

## Contrast Rules

- **Body text on background**: ≥ 4.5:1 (WCAG AA)
- **Large text (≥18px bold / ≥24px regular)**: ≥ 3:1
- **UI components and focus rings**: ≥ 3:1
- **Decorative / disabled**: no requirement, but keep legible

Quick reference — safe on white background:
- `#374151` (gray-700): 7.5:1 ✅
- `#4b5563` (gray-600): 5.9:1 ✅
- `#6b7280` (gray-500): 3.9:1 ⚠️ (large text only)
- `#9ca3af` (gray-400): 2.5:1 ❌ body text

## Color Application Rules

1. **Primary** — use sparingly (one dominant CTA per view). Overuse kills hierarchy.
2. **Semantic colors** — always pair color with an icon or text label for colorblind users.
3. **Backgrounds** — max 3 surface levels: base → card → overlay. Beyond 3 = visual noise.
4. **Gradients** — limit to hero sections and branded elements. Never on functional UI chrome.
5. **Opacity** — prefer `color-mix()` or named tokens over raw `rgba()` with magic values.

## Tailwind Color Config
```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',  // main
          600: '#2563eb',  // hover
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        secondary: {
          500: '#8b5cf6',
          600: '#7c3aed',
        },
      }
    }
  }
}
```
