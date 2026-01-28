# React UI Fix Sheet

**Created:** January 21, 2026
**Issues:** 4 bugs/UX improvements identified during testing

---

## Issue 1: Scaling Bug

**Symptom:** Elements off-screen at 100% browser scale, visible at 70%. Persists after page refresh.

**Likely Causes:**
- Fixed pixel widths instead of responsive units
- Missing `overflow: hidden` or `overflow: auto` on container
- Hardcoded viewport assumptions

**Where to Look:**
```bash
# Find fixed widths
grep -r "width:" src/App.tsx src/components/ --include="*.tsx"

# Find hardcoded pixels
grep -rE "width:\s*[0-9]+px" src/ --include="*.tsx"
```

**Suggested Fixes:**
```tsx
// BAD - fixed width
<div style={{ width: '400px' }}>

// GOOD - responsive
<div className="w-full max-w-md">  // Tailwind
<div style={{ width: '100%', maxWidth: '400px' }}>  // Inline
```

For the main container:
```tsx
// Ensure root container handles overflow
<div className="h-screen w-screen overflow-hidden">
  {/* or overflow-auto if scrolling needed */}
</div>
```

**Quick Test:**
1. Open DevTools → Toggle device toolbar (Ctrl+Shift+M)
2. Test at different viewport widths
3. Look for elements with `position: fixed` or `position: absolute` that don't respect viewport

---

## Issue 2: Text Input Overflow

**Symptom:** Text goes beyond margin instead of wrapping vertically (should stack like chatroom).

**Likely Causes:**
- `white-space: nowrap` on input container
- Missing `word-wrap: break-word` or `overflow-wrap: break-word`
- Textarea not expanding with content

**Where to Look:**
```bash
# Find the chat input component
grep -r "textarea\|TextArea\|input" src/ --include="*.tsx" | grep -i chat
```

**Suggested Fixes:**
```tsx
// For textarea - ensure it wraps and grows
<textarea
  className="w-full resize-none overflow-y-auto break-words"
  style={{
    wordWrap: 'break-word',
    overflowWrap: 'break-word',
    whiteSpace: 'pre-wrap',  // Preserves newlines but wraps
  }}
  rows={1}
  onInput={(e) => {
    // Auto-expand height
    e.currentTarget.style.height = 'auto';
    e.currentTarget.style.height = e.currentTarget.scrollHeight + 'px';
  }}
/>
```

Tailwind version:
```tsx
<Textarea
  className="w-full min-h-[40px] max-h-[200px] resize-none break-words whitespace-pre-wrap"
/>
```

**Key CSS Properties:**
```css
.chat-input {
  word-wrap: break-word;
  overflow-wrap: break-word;
  white-space: pre-wrap;
  max-width: 100%;
}
```

---

## Issue 3: Conversation Naming

**Symptom:** No way to rename conversations (want to label as "chasing confidence" etc.)

**Implementation Options:**

### Option A: Quick Inline Edit
```tsx
// In conversation list item
const [isEditing, setIsEditing] = useState(false);
const [name, setName] = useState(conversation.name || conversation.id.slice(0, 8));

return isEditing ? (
  <input
    value={name}
    onChange={(e) => setName(e.target.value)}
    onBlur={() => {
      saveConversationName(conversation.id, name);
      setIsEditing(false);
    }}
    onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
    autoFocus
  />
) : (
  <span onDoubleClick={() => setIsEditing(true)}>
    {name}
  </span>
);
```

### Option B: Context Menu
```tsx
// Right-click to rename
<ContextMenu>
  <ContextMenuTrigger>{conversationName}</ContextMenuTrigger>
  <ContextMenuContent>
    <ContextMenuItem onClick={() => setIsEditing(true)}>
      Rename
    </ContextMenuItem>
  </ContextMenuContent>
</ContextMenu>
```

### Backend Support Needed:
```python
# In conversation_manager.py or API
def rename_conversation(self, conversation_id: str, new_name: str):
    # Store in metadata or dedicated field
    self.orchestrator.update_context_metadata(
        conversation_id,
        {"display_name": new_name}
    )
```

**API Endpoint:**
```python
@app.post("/conversation/{id}/rename")
async def rename_conversation(id: str, body: RenameRequest):
    conversation_manager.rename_conversation(id, body.name)
    return {"success": True}
```

---

## Issue 4: Sidebar Organization

**Symptom:** All sidebars show as "active", many test sidebars, feels like junk drawer.

**Problems to Solve:**
1. Distinguish real work from test data
2. Sort/group sidebars meaningfully
3. Show actual status (active vs paused vs merged)

### Fix A: Status-Based Grouping
```tsx
const groupedSidebars = useMemo(() => {
  const active = sidebars.filter(s => s.status === 'active');
  const paused = sidebars.filter(s => s.status === 'paused');
  const merged = sidebars.filter(s => s.status === 'merged');
  return { active, paused, merged };
}, [sidebars]);

return (
  <div>
    <CollapsibleSection title={`Active (${groupedSidebars.active.length})`}>
      {groupedSidebars.active.map(s => <SidebarItem key={s.id} {...s} />)}
    </CollapsibleSection>
    <CollapsibleSection title={`Paused (${groupedSidebars.paused.length})`} defaultClosed>
      {groupedSidebars.paused.map(s => <SidebarItem key={s.id} {...s} />)}
    </CollapsibleSection>
    {/* etc */}
  </div>
);
```

### Fix B: Title/Date Sorting
```tsx
const sortedSidebars = useMemo(() => {
  return [...sidebars].sort((a, b) => {
    // Sort by: active first, then by last activity
    if (a.status === 'active' && b.status !== 'active') return -1;
    if (b.status === 'active' && a.status !== 'active') return 1;
    return new Date(b.lastActivity) - new Date(a.lastActivity);
  });
}, [sidebars]);
```

### Fix C: Nested Folder Style
```tsx
// Group by parent context
const sidebarTree = buildTree(sidebars); // Uses parent_context_id

return (
  <TreeView>
    {sidebarTree.map(node => (
      <TreeNode key={node.id} node={node}>
        {node.children?.map(child => (
          <TreeNode key={child.id} node={child} indent />
        ))}
      </TreeNode>
    ))}
  </TreeView>
);
```

### Fix D: Hide/Archive Test Data
```tsx
// Add "archive" or "hide" action
<ContextMenuItem onClick={() => archiveSidebar(sidebar.id)}>
  Archive (hide from list)
</ContextMenuItem>

// Filter in display
const visibleSidebars = sidebars.filter(s => !s.archived);
```

### Status Indicators
```tsx
const statusColors = {
  active: 'bg-green-500',
  paused: 'bg-yellow-500',
  merged: 'bg-blue-500',
  archived: 'bg-gray-400',
};

<span className={`w-2 h-2 rounded-full ${statusColors[sidebar.status]}`} />
```

---

## Quick Wins (Start Here)

1. **Scaling bug**: Add `overflow-hidden` to root container, check for fixed widths
2. **Text overflow**: Add `break-words whitespace-pre-wrap` to textarea
3. **Conversation naming**: Double-click to edit inline (frontend only first)
4. **Sidebar org**: Add status color dots + sort by status then date

---

## Files to Check

```
src/
├── App.tsx                 # Main layout, likely scaling issue
├── components/
│   ├── ChatInput.tsx       # Text overflow issue
│   ├── ConversationList.tsx # Naming + sidebar org
│   ├── SidebarList.tsx     # Sidebar organization
│   └── MessageBubble.tsx   # May also have overflow issues
```

---

## Testing After Fixes

1. **Scaling**: Test at 100%, 125%, 150% browser zoom
2. **Text wrap**: Type a very long message without spaces, verify wrap
3. **Naming**: Double-click conversation, rename, refresh, verify persists
4. **Sidebar**: Create test sidebar, verify correct status, verify sorting

Good luck! These should all be < 30 min fixes each.
