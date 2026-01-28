# Session Notes - January 2, 2026

## What We Discovered

### The App.tsx Situation
There are **multiple App files** and confusion about which is THE app:

| File | Status | Style | Uses Components? |
|------|--------|-------|------------------|
| `App.tsx` | **RUNS** (main.tsx imports it) | Inline styles, 926 lines | NO - has everything inline |
| `App.template-full-featured.tsx` | Template | Tailwind/shadcn | YES - uses our polished components |
| `App.xterm-only.tsx` | Template | Tailwind | Partial |
| `App.chat-only.tsx` | Template | ? | ? |
| `App.hybrid.tsx` | Template | ? | ? |
| `App.backup-*.tsx` | Backups | - | - |

**Key issue:** The running app (`App.tsx`) doesn't use the components we just fixed. It has its own inline implementations of everything.

**Decision needed:** Keep App.tsx and refactor it? Or switch to App.template-full-featured.tsx?

---

## What We Fixed (TypeScript Clean Build)

### Components Upgraded to Radix
- [x] `tabs.tsx` - Now uses `@radix-ui/react-tabs` (was using cloneElement hack)
- [x] `collapsible.tsx` - Already Radix
- [x] `tooltip.tsx` - Already Radix
- [x] `scroll-area.tsx` - Already Radix

### Components Wired Up (were unused)
- [x] `ErrorPanel.tsx` - Added expand/collapse controls, "Expand Criticals" button
- [x] `EventStreamPanel.tsx` - Added event type icons, tooltips, stats display
- [x] `ServiceStatusPanel.tsx` - Added refresh indicator (isRefreshing)
- [x] `App.template-full-featured.tsx` - Added CardHeader/CardTitle, swapped Input→Textarea

### Imports Cleaned Up
- [x] `TerminalDisplay.tsx` - Removed unused React, fixed `selection`→`selectionBackground`
- [x] `progress.tsx` - Removed unused React import
- [x] `separator.tsx` - Removed unused React import
- [x] `FileUploadPanel.tsx` - Removed unused Trash2 (X icon is correct for "remove from list")
- [x] `App.xterm-only.tsx` - Removed unused React import
- [x] `websocket_message_types.ts` - Fixed duplicate `source` property

---

## Still TODO

### 1. Progress & Separator - Upgrade to Radix
Currently simplified versions. User approved upgrading to Radix standard for consistency.
- `src/components/ui/progress.tsx`
- `src/components/ui/separator.tsx`

### 2. cn() Consistency
Some components use `cn()` utility, others use template literals.
**Question:** Do both patterns serve different purposes, or should we standardize?
- Need to review if any template literal usage is intentional

### 3. Decide on App.tsx
**Options:**
1. Keep `App.tsx` (inline monolith) and gradually refactor
2. Switch to `App.template-full-featured.tsx` as new App.tsx
3. Keep both and document when to use which

### 4. Visual Testing
Haven't run `npm run dev` to verify UI works. Type-safe ≠ working UI.

### 5. Break Up Template Monolith
`App.template-full-featured.tsx` is ~500 lines. Could be split into smaller pieces.

---

## Claude's Needs (AI Transparency)

Things that would help ME work more effectively:

### High Priority
1. **Which App is THE app** - Now documented above, but decision still needed
2. **What's placeholder vs real** - Need to mark simulated code clearly
3. **Runtime flow map** - "What calls what" diagram would help reasoning

### Medium Priority
4. **cn() pattern decision** - Standardize or keep both?
5. **File naming convention** - templates vs backups vs actual

### Low Priority
6. **Progress/Separator Radix upgrade** - Nice to have, not blocking

---

## API Endpoints (from App.tsx)

The running app uses these endpoints:
```
GET  /health           - Connection check
GET  /history          - Load conversation history
GET  /services/dashboard - Service status
GET  /errors           - Error list
GET  /memory/stats     - Memory system stats
POST /chat             - Send message
POST /errors/clear     - Clear errors
POST /errors/{id}/acknowledge - Acknowledge error
```

**Question:** Is the backend defined? Does it exist? Or is it placeholder?

---

## Concepts Explained This Session

### Props
Properties passed to React components - like function arguments:
```tsx
<Button variant="primary" size="sm">  // variant and size are props
```

### Context vs cloneElement
- **Old way (cloneElement):** Parent secretly injects props into children
- **New way (Context):** Children explicitly "reach up" to get shared state
- Radix components use Context internally

---

## Files Modified This Session

```
src/components/ui/tabs.tsx          - Radix upgrade
src/components/ui/progress.tsx      - Removed React import
src/components/ui/separator.tsx     - Removed React import
src/components/ErrorPanel.tsx       - Added expand controls
src/components/EventStreamPanel.tsx - Added tooltips, icons, stats
src/components/ServiceStatusPanel.tsx - Added refresh indicator
src/components/FileUploadPanel.tsx  - Removed Trash2 import
src/components/TerminalDisplay.tsx  - Fixed React import, selection theme
src/App.template-full-featured.tsx  - Added CardHeader, swapped to Textarea
src/App.xterm-only.tsx              - Removed React import
src/types/websocket_message_types.ts - Fixed duplicate source
CHAT_UI_WISHLIST.md                 - Created, documented features
```

---

## Tomorrow's Starting Point

1. **Decide:** Which App to use going forward?
2. **Quick wins:** Upgrade Progress/Separator to Radix
3. **Review:** API - is backend real or stubbed?
4. **Optional:** Visual test with `npm run dev`

---

*Session ended: User needs sleep. All TypeScript errors resolved. Clean build achieved.*
