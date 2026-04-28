## Skill: Next.js 14 (App Router)

You are building a Next.js 14+ application using the App Router. Follow these conventions:

- Place all routes in `app/` directory; `page.tsx` defines a route, `layout.tsx` wraps it
- Server Components by default; use `"use client"` only when browser APIs or state are needed
- API routes in `app/api/[route]/route.ts` using `NextRequest`/`NextResponse`
- Data fetching: `fetch()` with `cache: 'no-store'` or `revalidate` in Server Components
- Use `next/image` for images, `next/link` for navigation
- Environment variables: `NEXT_PUBLIC_` prefix for client-side access
- TypeScript throughout; define types in `types/` directory
- `npm run dev` to start development server on port 3000
