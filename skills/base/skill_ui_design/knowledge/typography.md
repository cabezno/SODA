# Typography for UI Design

## Font Selection by Project Type

| Project Type | Heading Font | Body Font | Mono Font |
|-------------|-------------|-----------|-----------|
| SaaS / B2B | Inter | Inter | JetBrains Mono |
| Consumer / Social | Plus Jakarta Sans | Inter | — |
| Developer Tool | JetBrains Mono | Inter | JetBrains Mono |
| Marketing Site | Clash Display / Sora | Inter | — |
| E-commerce | Inter / Outfit | Inter | — |
| Dashboard | Inter | Inter | Fira Code |

**Default stack (works everywhere):**
```css
--font-sans: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
--font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
```

## Type Scale (Major Third — 1.25×)

```css
:root {
  --text-xs:   0.75rem;    /* 12px — captions, badges */
  --text-sm:   0.875rem;   /* 14px — secondary text, labels */
  --text-base: 1rem;       /* 16px — body copy */
  --text-lg:   1.125rem;   /* 18px — lead text, card titles */
  --text-xl:   1.25rem;    /* 20px — section subheadings */
  --text-2xl:  1.5rem;     /* 24px — page subheadings */
  --text-3xl:  1.875rem;   /* 30px — section headings */
  --text-4xl:  2.25rem;    /* 36px — page headings */
  --text-5xl:  3rem;       /* 48px — hero headings */
  --text-6xl:  3.75rem;    /* 60px — display headings */
}
```

## Font Weight System

```css
:root {
  --font-normal:    400;  /* body, descriptions */
  --font-medium:    500;  /* labels, nav items, table headers */
  --font-semibold:  600;  /* card titles, secondary headings */
  --font-bold:      700;  /* page headings, CTAs, emphasis */
  --font-extrabold: 800;  /* hero headings, display numbers */
}
```

## Line Height Rules

```css
:root {
  --leading-tight:   1.25;  /* headings, display */
  --leading-snug:    1.375; /* subheadings */
  --leading-normal:  1.5;   /* body copy (default) */
  --leading-relaxed: 1.625; /* long-form articles */
  --leading-loose:   2;     /* open, airy layouts */
}
```

**Rule**: Heading line-height ≤ 1.3. Body line-height 1.5–1.6. Never use `line-height: 1` for multi-line text.

## Letter Spacing

```css
:root {
  --tracking-tighter: -0.05em;  /* large display headings */
  --tracking-tight:   -0.025em; /* headings ≥36px */
  --tracking-normal:   0em;     /* body, default */
  --tracking-wide:     0.025em; /* labels, small caps */
  --tracking-wider:    0.05em;  /* uppercase labels, badges */
  --tracking-widest:   0.1em;   /* overlines, CAPS */
}
```

**Rule**: Tighten letter-spacing on large headings (≥32px), loosen on uppercase labels.

## Semantic HTML + CSS Mapping

```css
h1 { font-size: var(--text-4xl); font-weight: var(--font-bold);     line-height: var(--leading-tight);  letter-spacing: var(--tracking-tight); }
h2 { font-size: var(--text-3xl); font-weight: var(--font-bold);     line-height: var(--leading-tight); }
h3 { font-size: var(--text-2xl); font-weight: var(--font-semibold); line-height: var(--leading-snug); }
h4 { font-size: var(--text-xl);  font-weight: var(--font-semibold); line-height: var(--leading-snug); }
h5 { font-size: var(--text-lg);  font-weight: var(--font-medium);   line-height: var(--leading-normal); }
h6 { font-size: var(--text-base);font-weight: var(--font-medium);   line-height: var(--leading-normal); }
p  { font-size: var(--text-base);font-weight: var(--font-normal);   line-height: var(--leading-normal); }
```

## Responsive Typography

Use `clamp()` for fluid scaling:
```css
h1 { font-size: clamp(var(--text-3xl), 5vw, var(--text-5xl)); }
h2 { font-size: clamp(var(--text-2xl), 4vw, var(--text-4xl)); }
h3 { font-size: clamp(var(--text-xl),  3vw, var(--text-3xl)); }
```

Fixed responsive scaling (if clamp not preferred):
```css
/* Mobile first */
h1 { font-size: var(--text-3xl); }
@media (min-width: 768px)  { h1 { font-size: var(--text-4xl); } }
@media (min-width: 1024px) { h1 { font-size: var(--text-5xl); } }
```

## Google Fonts Import Pattern

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

Always use `display=swap` to prevent FOIT (Flash of Invisible Text).

## Typography Anti-Patterns (never do)

- Never use more than 2 typeface families in one project.
- Never use `font-size` < 12px for readable text.
- Never mix bold weights arbitrarily — define a clear hierarchy.
- Never use `text-transform: uppercase` on body text.
- Never use centered text for blocks longer than 3 lines.
- Max line length: 65–75 characters (approx. `max-width: 65ch`).
