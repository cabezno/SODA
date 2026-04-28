# Design Systems Reference

## When to Use Which System

| System | Best For | Stack | File Size |
|--------|----------|-------|-----------|
| **Tailwind CSS** | Custom designs, full control, any stack | Any | Purged: ~5KB |
| **shadcn/ui** | React apps needing polished components fast | React + Tailwind | Tree-shaken |
| **Material UI (MUI)** | Enterprise/admin apps, Google ecosystem | React | ~300KB |
| **Chakra UI** | Developer-friendly, accessible by default | React | ~150KB |
| **DaisyUI** | Tailwind components, any framework | Any + Tailwind | Minimal |
| **Radix UI** | Headless primitives, own styling | React | Minimal |
| **Bootstrap 5** | Traditional HTML, quick prototypes | Any | ~200KB |
| **Ant Design** | Enterprise Chinese-style, data-heavy | React | ~400KB |

## Tailwind CSS Conventions

### Color Palette Setup (tailwind.config.js)
```js
theme: {
  extend: {
    colors: {
      primary: { 50: '#eff6ff', 500: '#3b82f6', 900: '#1e3a8a' },
      secondary: { 50: '#f5f3ff', 500: '#8b5cf6', 900: '#4c1d95' },
      success: '#22c55e', warning: '#f59e0b', danger: '#ef4444',
    }
  }
}
```

### Tailwind Component Patterns
```html
<!-- Button -->
<button class="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 
               focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2
               disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
  Label
</button>

<!-- Card -->
<div class="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 
            dark:border-gray-700 p-6">

<!-- Input -->
<input class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm
              focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent
              placeholder-gray-400">
```

### Dark Mode with Tailwind
- Use `class` strategy: `<html class="dark">`.
- Pair every color with dark variant: `bg-white dark:bg-gray-900`.
- Toggle via JS: `document.documentElement.classList.toggle('dark')`.

## shadcn/ui Conventions

### Installation Pattern
```bash
npx shadcn-ui@latest init
npx shadcn-ui@latest add button card input form table
```

### Component Usage
```tsx
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

// Always use cn() for conditional classes
import { cn } from "@/lib/utils"
<div className={cn("base-class", condition && "conditional-class")} />
```

### shadcn/ui File Structure
```
src/
  components/
    ui/          ← shadcn generated components (don't modify)
    [feature]/   ← your components using shadcn primitives
  lib/
    utils.ts     ← cn() utility
```

## Material UI (MUI) Conventions

### Theme Setup
```tsx
const theme = createTheme({
  palette: {
    primary: { main: '#1976d2' },
    secondary: { main: '#9c27b0' },
  },
  typography: { fontFamily: 'Inter, sans-serif' },
  shape: { borderRadius: 8 },
});
```

### sx Prop Pattern
```tsx
<Box sx={{ display: 'flex', gap: 2, p: 3, bgcolor: 'background.paper' }}>
<Typography variant="h5" sx={{ fontWeight: 700, color: 'text.primary' }}>
```

## CSS Variables Design Tokens (framework-agnostic)

Use for any project without a design system:
```css
:root {
  /* Colors */
  --color-primary: #3b82f6;
  --color-primary-dark: #2563eb;
  --color-secondary: #8b5cf6;
  --color-success: #22c55e;
  --color-warning: #f59e0b;
  --color-danger: #ef4444;
  --color-bg: #ffffff;
  --color-bg-secondary: #f8fafc;
  --color-text: #0f172a;
  --color-text-muted: #64748b;
  --color-border: #e2e8f0;

  /* Typography */
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
  --text-xs: 0.75rem;  --text-sm: 0.875rem; --text-base: 1rem;
  --text-lg: 1.125rem; --text-xl: 1.25rem;  --text-2xl: 1.5rem;
  --text-3xl: 1.875rem; --text-4xl: 2.25rem;

  /* Spacing (8px base) */
  --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem;
  --space-4: 1rem;    --space-6: 1.5rem; --space-8: 2rem;
  --space-12: 3rem;   --space-16: 4rem;

  /* Shadows */
  --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
  --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);

  /* Border radius */
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-full: 9999px;

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: #0f172a;
    --color-bg-secondary: #1e293b;
    --color-text: #f1f5f9;
    --color-text-muted: #94a3b8;
    --color-border: #334155;
  }
}
```
