# UI Component Patterns

## Navigation
- **Top nav**: horizontal brand + links. Use for marketing sites, simple apps (<6 sections).
- **Sidebar**: vertical, collapsible. Use for dashboards, admin panels, apps with >5 sections.
- **Bottom nav** (mobile): 3–5 primary actions, icon + label, thumb-zone friendly.
- **Breadcrumbs**: always for >2 depth hierarchies. Current page not clickable.
- **Tabs**: same-level content switching. Max 5–6 tabs; use dropdown overflow for more.

## Data Display
- **Table**: sortable columns, sticky header on scroll, row hover highlight, empty state message.
  Always include: pagination controls, row count, column visibility toggle for >6 columns.
- **Card grid**: equal height cards, consistent padding (16–24px), image ratio fixed (16:9 or 1:1).
- **List**: use for ranked/ordered items. Left-align metadata. Right-align actions.
- **Stats/KPI**: large number, small label below, trend indicator (↑↓ + %). Group by 3 or 4.
- **Timeline**: left border with dot markers. Alternate sides for dense content.

## Forms
- **Single-column layout**: always for mobile, preferred for focused tasks (checkout, onboarding).
- **Two-column layout**: only for related pairs (first name / last name, city / zip).
- **Stepper/Wizard**: for >4 fields or complex flows. Show progress bar + step count.
- **Inline edit**: click-to-edit for single values. Save/cancel appear on focus.
- **Search**: always debounce 300ms. Show spinner during search, "no results" state, recent searches.
- **File upload**: drag-and-drop zone + click fallback. Show file name, size, remove button.

## Feedback & Status
- **Toast notifications**: top-right, auto-dismiss 4s (errors: manual dismiss). Max 3 stacked.
- **Modal dialogs**: max width 480–640px. Overlay closes on click only for non-destructive.
  Destructive actions: explicit confirm button (red), cancel on left.
- **Skeleton loaders**: match the shape of content (not spinner alone for large areas).
- **Progress bars**: show % and ETA for long operations (>3s). Indeterminate for unknown duration.
- **Empty states**: illustration/icon + headline + description + primary CTA. Never blank.
- **Error states**: specific message (what happened + how to fix). Retry button always visible.

## Buttons & CTAs
- **Primary**: one per view/section. Filled, high contrast.
- **Secondary**: outlined or ghost. Paired with primary for cancel/back actions.
- **Destructive**: red/danger color. Requires confirmation step.
- **Icon buttons**: always include aria-label and tooltip on hover.
- **Loading state**: spinner replaces icon or label text. Disable during loading.
- **Button groups**: consistent size, same visual weight per group.

## Authentication Flows
- **Login**: email + password. "Show password" toggle. "Forgot password" link below field.
  Social login above divider "or". Remember me checkbox.
- **Register**: progressive (minimal first: email + password → profile details).
  Real-time password strength indicator. Terms checkbox with link.
- **Forgot password**: single email field. Success state hides form, shows confirmation message.
- **2FA**: numeric code input, auto-advance between digits. Resend timer (60s countdown).

## Dashboard Layouts
- **Analytics dashboard**: KPI row (4 stats) → main chart → secondary charts + table.
- **Admin dashboard**: sidebar nav + top bar (search, user menu) + content area with breadcrumbs.
- **App shell**: persistent nav + scrollable content. Avoid full-page reloads.
