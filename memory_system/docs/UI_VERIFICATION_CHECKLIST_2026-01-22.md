# UI Verification Checklist
**Date:** 2026-01-22
**Purpose:** Completionism check - verify all UI features are accurate and functioning
**Scope:** All React UI changes across sessions (Jan 5 → Jan 22)

---

## Quick Reference - What's Automated vs Manual

| Area | Automated (pytest) | Manual (this checklist) |
|------|--------------------|-----------------------|
| API endpoints | test_sidebar_api_features.py | - |
| Data model | test_sidebar_api_features.py | - |
| Orchestrator workflows | test_sidebar_workflows.py | - |
| CSS/layout | - | Sections 1-2 below |
| React component behavior | - | Sections 3-8 below |
| Visual rendering | - | All sections below |

---

## 1. Layout & Scaling

- [ ] **No horizontal scroll** at 100% zoom
- [ ] **No horizontal scroll** at 125% zoom
- [ ] **No horizontal scroll** at 150% zoom
- [ ] **Window resize** - sidebar doesn't push content off-screen
- [ ] **Root container** has `w-screen overflow-hidden` (inspect element)
- [ ] **Mobile width** (~375px) - layout degrades gracefully (no overlap/clip)

---

## 2. Text Input (Textarea)

- [ ] **Long text wraps** - type 200+ chars without Enter, text wraps to next line
- [ ] **Textarea grows** - height increases as lines wrap (up to 200px max)
- [ ] **Max height caps** - after 200px, internal scroll instead of infinite growth
- [ ] **Shift+Enter** - adds newline within message
- [ ] **Enter** (no shift) - sends message
- [ ] **Height resets** - after send, textarea shrinks back to single-line height
- [ ] **No horizontal scroll** - text never scrolls horizontally inside the input
- [ ] **Paste multiline** - pasting multi-line text grows textarea appropriately

---

## 3. Sidebars Panel - List View

- [ ] **Tab visible** - "Sidebars" tab present in panel
- [ ] **Count badge** - tab shows context count (if > 0)
- [ ] **Empty state** - with no sidebars shows "No sidebars yet..." message
- [ ] **Context list** - each item shows:
  - [ ] Display name or task_description
  - [ ] Status badge (correct color per status)
  - [ ] Tags (if any, as badges below name)
  - [ ] Exchange count indicator
- [ ] **Refresh button** - reloads list from API
- [ ] **"New" button** - opens spawn form with reason input

### Status Colors (verify each)
| Status | Expected Color | Checked |
|--------|---------------|---------|
| active | Grey/default | [ ] |
| paused | Blue/secondary | [ ] |
| waiting | Blue/secondary | [ ] |
| testing | Blue/secondary | [ ] |
| reviewing | Blue/secondary | [ ] |
| spawning_child | Blue/secondary | [ ] |
| consolidating | Blue/secondary | [ ] |
| merged | Dim grey/outline | [ ] |
| archived | Dim grey/outline | [ ] |
| failed | Red/destructive | [ ] |

---

## 4. Sidebars Panel - Tree View

- [ ] **Toggle button** - switches between list and tree view
- [ ] **Tree rendering** - parent-child nesting visible with indentation
- [ ] **Nested levels** - 3+ level nesting renders correctly
- [ ] **Collapse/expand** - tree nodes can be collapsed
- [ ] **Active highlight** - active context has ring/highlight

---

## 5. Sidebars Panel - Pagination

- [ ] **"1-50 of X"** displays at bottom of list
- [ ] **Next (>)** button loads next page
- [ ] **Count updates** - shows "51-100 of X" on page 2
- [ ] **Prev (<)** button goes back
- [ ] **Next disabled** at end of list
- [ ] **Prev disabled** on page 1
- [ ] **Page reset** - navigating away and back resets to page 1 (known behavior)

---

## 6. Sidebars Panel - Rename (Alias)

- [ ] **Double-click name** - inline input appears
- [ ] **Pencil icon click** - inline input appears
- [ ] **Type new name** - input accepts text
- [ ] **Enter/checkmark** - saves alias, list updates
- [ ] **Escape/X** - cancels without saving
- [ ] **Display updates** - new alias shows in list immediately
- [ ] **Your alias shows** - the human's alias displays (not claude's)

---

## 7. Sidebars Panel - Tags UI

- [ ] **"no tags" text** visible on untagged contexts (with Tag icon)
- [ ] **Pencil icon** next to tags area
- [ ] **Click edit** - input field appears for comma-separated tags
- [ ] **Enter tags** - type "debugging, auth, testing" and press Enter
- [ ] **Tags as badges** - after save, tags display as individual badges
- [ ] **Edit again** - can re-open and modify tags
- [ ] **Remove a tag** - editing to fewer tags removes the old ones
- [ ] **Empty submit** - clearing all tags and saving shows "no tags" again

---

## 8. Sidebars Panel - Browse Aliases

- [ ] **"aliases" link** (Users icon) visible below tags on aliased contexts
- [ ] **Click expands** - shows panel with all actors and their current alias
- [ ] **History count** - shows "(2 versions)" or similar for actors with history
- [ ] **Click again** - closes the expanded panel
- [ ] **Multiple actors** - shows both "human" and "claude" aliases if both exist

---

## 9. Sidebars Panel - Bulk Archive

- [ ] **Red trash icon** in panel header
- [ ] **Click opens** - bulk archive panel/modal appears
- [ ] **"Empty only" checkbox** - option to filter by exchange count
- [ ] **"Preview" button** - shows count of what would be archived
- [ ] **Preview count** - displays "Would archive X contexts"
- [ ] **"Archive X" button** - executes (shows confirmation first?)
- [ ] **Success message** - includes batch_id after execution
- [ ] **List updates** - archived items disappear from active list on refresh

---

## 10. SidebarControlBar (Above Chat Input)

- [ ] **Renders** - control bar visible above chat input area
- [ ] **Breadcrumb** - shows "Main" with home icon when no active context
- [ ] **Breadcrumb path** - shows "Main > Context Name" when in sidebar
- [ ] **Status badge** - hover shows tooltip with `{reason}: {status}`
- [ ] **Fork button** - click expands inline input
- [ ] **Fork input** - type reason + Enter creates sidebar, input closes
- [ ] **Fork cancel** - Escape closes input without creating
- [ ] **Back button** - visible when in a sidebar, navigates to parent
- [ ] **Exchange counts** - shows "X local + Y inherited" format

---

## 11. Action Buttons (Per Context)

For each status, verify correct action buttons appear:

| Status | Focus | Pause | Resume | Merge | Archive |
|--------|-------|-------|--------|-------|---------|
| active | - | [x] | - | [x]* | [x] |
| paused | [x] | - | [x] | [x]* | [x] |
| waiting | [x] | - | [x] | [x]* | [x] |
| testing | [x] | [x] | - | [x]* | [x] |
| reviewing | [x] | - | - | [x]* | [x] |
| spawning_child | [x] | - | - | - | [x] |
| consolidating | [x] | - | - | - | [x] |
| merged | - | - | - | - | [x] |
| archived | - | - | - | - | - |
| failed | - | - | - | - | [x] |

*Merge only if context has a parent

- [ ] Verified active context buttons
- [ ] Verified paused context buttons
- [ ] Verified merged context (archive only)
- [ ] Verified archived context (no actions)
- [ ] Verified failed context (archive only)

---

## 12. Completed Section

- [ ] **Collapsible section** at bottom of sidebars list
- [ ] **Contains** merged and archived contexts
- [ ] **Collapsed by default** (or shows count when collapsed)
- [ ] **Click to expand** - shows completed contexts
- [ ] **Correct status badges** - merged/archived show dim styling

---

## 13. Error States

- [ ] **API unreachable** - UI shows error state, doesn't crash
- [ ] **Slow response** - loading indicator visible
- [ ] **Empty reason on spawn** - button disabled or validation shown
- [ ] **Special characters in reason** - properly escaped, no XSS
- [ ] **Rapid clicks** - debounced, no duplicates created
- [ ] **Console errors** - open DevTools console during all tests above, note any errors

---

## 14. WebSocket Live Updates

When sidebar actions occur, verify UI updates without manual refresh:

- [ ] **Spawn** - new sidebar appears in list
- [ ] **Focus change** - highlight moves to new active
- [ ] **Pause** - status badge updates to blue
- [ ] **Resume** - status badge updates to grey
- [ ] **Merge** - context moves to completed section
- [ ] **Archive** - context moves to completed section

---

## Notes / Issues Found

| # | Section | Issue | Severity |
|---|---------|-------|----------|
| 1 | | | |
| 2 | | | |
| 3 | | | |

---

## Sign-off

- [ ] All sections checked
- [ ] No console errors observed
- [ ] WebSocket updates working
- [ ] All action buttons correct per status
- [ ] CSS/layout solid at multiple zoom levels

Tested by: _________________ Date: _________________
