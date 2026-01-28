# Chat UI Wishlist

Features we want to add to the chat interface for holistic transparency.

## For Operator (Human)

### Quick Context Peek
- Hover or button on any AI response to see what context/memory was used
- Shows confidence scores, source documents, retrieval scores
- Non-intrusive - doesn't interrupt conversation flow

### Branch Button
- Fork conversation at any exchange
- "What if I had asked this differently?"
- Useful for exploring alternative reasoning paths

### "Go Deeper" Action
- Button on any AI response to request elaboration
- Quick way to drill down without typing full questions
- Could have presets: "Explain more", "Show examples", "What are the risks?"

### Highlight-to-Ask
- Select text in AI response, get contextual actions
- "Clarify this", "Expand on this", "I disagree with this"
- Reduces friction for follow-up questions

### Pin Exchanges
- Mark specific exchanges as important
- Pinned items stay visible/accessible
- Useful for reference during long conversations

### Conversation Bookmarks
- Named bookmarks at specific points in conversation
- Jump back to key moments
- "Bookmark: When we decided on the architecture"

## For AI (Claude)

### Confidence Display
- Visual indicator of AI confidence per statement
- Traffic light or gradient: high/medium/low confidence
- Helps operator calibrate trust appropriately

### Context Source Badges
- Small badges showing where information came from
- "From: episodic memory", "From: working context", "From: training"
- Transparency about knowledge sources

### Uncertainty Flag
- Explicit marker when AI is uncertain or guessing
- "I'm not sure about this, but..."
- Better than hiding uncertainty in hedging language

### Related Memory Sidebar
- Show what memories were triggered by current exchange
- Helps AI (and operator) understand association chains
- Could reveal unexpected connections

### Request More Context Button
- AI can signal when it needs more information
- "I could answer better if I knew X"
- Makes AI needs visible to operator

## For Both

### Exchange Annotations
- Either party can add notes to exchanges
- "This was wrong", "Good insight", "Revisit later"
- Builds shared understanding over time

### Search Within Chat
- Find specific exchanges by keyword
- Filter by: time, speaker, topic, confidence level
- Essential for long conversations

### Export/Snapshot
- Save conversation state at any point
- Export in various formats (markdown, JSON, annotated)
- For documentation, review, or resumption

### Collaborative Editing Mode
- Both parties can suggest edits to exchanges
- "Let me rephrase what I meant..."
- Reduces misunderstanding propagation

## Implementation Priority

### Phase 1 (MVP)
- [x] Confidence display - DONE (Jan 3, 2026)
- [ ] Context source badges
- [ ] Search within chat

### Phase 2 (Enhanced Transparency)
- [ ] Quick context peek
- [ ] Uncertainty flag
- [ ] Exchange annotations

### Phase 3 (Power Features)
- [ ] Branch button
- [ ] Highlight-to-ask
- [ ] Related memory sidebar

### Phase 4 (Polish)
- [ ] Pin exchanges
- [ ] Conversation bookmarks
- [ ] Export/snapshot

---

## Already Implemented

### ErrorPanel Expand Controls
- [x] Expand All / Collapse All buttons
- [x] "Expand Criticals" - one-click to show all critical errors
- [x] Controlled collapsible groups with visual state (chevron direction)
- *Location: `src/components/ErrorPanel.tsx`*

### EventStreamPanel
- [x] Tier filtering (critical/system/debug)
- [x] Pause/resume stream
- [x] Search and type filter
- [x] Exponential backoff reconnection
- [x] Event type icons (memory, error, context, etc.)
- [x] Event type tooltips with descriptions from backend
- [x] Emitter stats display in footer (when requested)
- *Location: `src/components/EventStreamPanel.tsx`*

### MessageBubble Component (Jan 3, 2026)
- [x] Extracted from App.tsx into reusable component
- [x] Confidence display with color-coded icons
- [x] Tunable confidence thresholds (high/good/medium/low)
- [x] Debug panel for retrieved memories
- *Location: `src/components/MessageBubble.tsx`*

### UI Enhancements (Jan 3, 2026)
- [x] Latency display in header (color-coded: grey/yellow/red)
- [x] Scroll-to-bottom button for chat
- [x] Dark theme color palette (grey=ok, blue=suspicious, red=bad)
- [x] ErrorPanel filter buttons fit properly (flex-1)

---

## Technical Debt / Next Session

### Pending Decisions
- [x] **Which App.tsx to use?** - RESOLVED: Keep App.tsx, convert to Tailwind, use components
- [ ] **cn() pattern standardization** - Both patterns exist, need to decide if intentional

### Component Upgrades
- [x] `progress.tsx` - Upgraded to Radix (Jan 3, 2026)
- [x] `separator.tsx` - Upgraded to Radix (Jan 3, 2026)
- [x] `tabs.tsx` - Upgraded to Radix (Jan 2, 2026)

### Verification Needed
- [x] Visual test (`npm start`) - UI renders correctly
- [ ] API backend status - Real endpoints or stubs?
- [ ] Test with running backend services

---

*Last updated: 2026-01-03*
*Source: Discussion about what UI features would help both operator and AI work together effectively*
