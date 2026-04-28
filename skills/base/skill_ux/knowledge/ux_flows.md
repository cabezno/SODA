# UX Flows & Interaction Patterns

## Core Interaction Principles
- **Immediate feedback**: response within 100ms (instant feel), 1s (loading indicator), >3s (progress bar + cancel).
- **Optimistic UI**: update UI immediately, revert on error. Show subtle "saving…" state.
- **Undo over confirm**: prefer undo for recoverable actions (move, archive) vs. confirm for destructive (delete, send).
- **Progressive disclosure**: show 80% use cases upfront. "Advanced options" accordion/link for the rest.
- **Error prevention > error recovery**: disable invalid actions, validate before submit, confirm ambiguous actions.

## Onboarding Flows
- Max 3–5 screens for first-run onboarding.
- Show value proposition first, ask for data second.
- Skip option always visible. Progress indicator mandatory.
- Completion: celebrate with success state → land on main feature.
- Return users: skip onboarding entirely.

## Search & Filter UX
- **Search**: instant results on type (debounce 300ms). Highlight matched terms. Recent + suggested.
- **Filters**: show active filter count on collapsed state. Clear all button. Apply on change (no submit button for simple filters).
- **Sort**: default sort labeled. Active sort column highlighted. Clicking again reverses order.
- **Pagination vs. infinite scroll**: pagination for tables/structured data; infinite scroll for feeds/social.
- **Empty results**: "No results for X" + clear filters button + suggestions.

## CRUD Flows
- **Create**: drawer/modal for simple forms (<5 fields). Full page for complex forms.
  Success → stay on list with item highlighted, or navigate to new item detail.
- **Read/Detail**: breadcrumb back to list. Related items section. Actions (edit, delete) in header.
- **Edit**: inline editing for single fields. Form for multiple fields. Autosave where appropriate.
  Unsaved changes warning on navigation away.
- **Delete**: confirm dialog with item name to avoid ambiguity. Undo option 5–10s after deletion.

## Notification & Alert Patterns
- **System alerts** (outage, maintenance): full-width banner, dismissible, top of page.
- **Action feedback** (save, delete): toast bottom-right or top-right.
- **Validation errors**: inline below field, red border. Summary at top of form for >3 errors.
- **Success states**: green checkmark + message. Auto-dismiss or manual.
- **Warning states**: amber, non-blocking. User can proceed but is informed.

## Mobile UX Patterns
- **Pull to refresh**: native feel for lists/feeds.
- **Swipe actions**: reveal actions (delete/archive) on horizontal swipe. Show hint on first use.
- **Bottom sheet**: replaces modals on mobile. Handle bar for drag. Partial → full expansion.
- **Floating action button (FAB)**: primary action only. Bottom-right. Disappears on scroll down, reappears on scroll up.
- **Sticky CTAs**: primary button sticks to bottom on forms/checkout.
- **Haptic feedback**: subtle vibration on destructive actions and confirmations.

## Accessibility Interaction Patterns
- **Keyboard navigation**: Tab order matches visual order. Trap focus in modals.
- **Skip links**: "Skip to content" as first focusable element.
- **Announce changes**: ARIA live regions for dynamic content (search results, notifications).
- **Focus management**: after modal close, return focus to trigger element.
- **Screen reader labels**: all icon buttons, inputs without visible labels, status indicators.

## State Management in UI
Every interactive element needs ALL states designed:
- Default / hover / active / focus / disabled
- Loading / success / error / empty
- Selected / unselected (for toggles, checkboxes, filters)
Never leave a state undesigned — empty/loading/error are as important as the happy path.
