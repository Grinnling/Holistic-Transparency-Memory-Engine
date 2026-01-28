# DRAFT: Conversation Manager Integration Options

**Purpose:** Figure out where the conversation management code from rich_chat.py should live.

---

## What We're Extracting from rich_chat.py

```python
# ~290 lines total
def start_new_conversation(self)      # Generate UUID, clear history
def list_conversations(self)          # Query episodic memory API
def switch_conversation(self, id)     # Load from episodic memory
def restore_conversation_history(self) # Pull from working + episodic
def get_recent_context_hint(self)     # Local state lookup
```

---

## OPTION A: Merge into conversation_orchestrator.py

**Philosophy:** One place for all conversation/context operations.

```python
# conversation_orchestrator.py (expanded)

class ConversationOrchestrator:
    """
    Handles:
    - Session context (in-memory sidebars)
    - OZOLITH logging (audit trail)
    - Episodic memory persistence (NEW)
    """

    def __init__(self, error_handler=None, service_manager=None):
        # Existing
        self._contexts: Dict[str, SidebarContext] = {}
        self._active_context_id: Optional[str] = None
        self.registry = get_registry()
        self.error_handler = error_handler

        # NEW: For episodic memory
        self.service_manager = service_manager
        self.conversation_id: Optional[str] = None  # Current persistent ID

    # === EXISTING (in-memory + OZOLITH) ===
    def create_root_context(self, ...) -> str: ...
    def spawn_sidebar(self, ...) -> str: ...
    def add_exchange(self, ...) -> str: ...
    def merge_sidebar(self, ...) -> Dict: ...
    # etc.

    # === NEW: Episodic Memory Integration ===

    def start_new_conversation(self, task_description: str = None) -> str:
        """
        Start fresh conversation - both in-memory AND persistent.
        """
        # Generate persistent conversation ID
        self.conversation_id = str(uuid.uuid4())

        # Create root context (existing - logs to OZOLITH)
        context_id = self.create_root_context(
            task_description=task_description,
            created_by="human"
        )

        # Link persistent ID to context
        context = self._contexts[context_id]
        context.extra["persistent_conversation_id"] = self.conversation_id

        return context_id

    def list_conversations(self) -> List[Dict]:
        """
        List past conversations from episodic memory.
        """
        if not self._check_episodic_health():
            return []

        response = requests.get(
            f"{self._get_episodic_url()}/recent?limit=50",
            headers=self._get_trace_headers(),
            timeout=5
        )

        if response.status_code == 200:
            return response.json().get('conversations', [])
        return []

    def switch_conversation(self, target_id: str) -> bool:
        """
        Switch to different conversation from episodic memory.
        Creates new root context with loaded history.
        """
        # Load from episodic
        history = self._load_from_episodic(target_id)
        if not history:
            return False

        # Create new root context
        context_id = self.create_root_context(
            task_description=f"Resumed: {target_id[:8]}..."
        )

        # Populate with loaded history
        context = self._contexts[context_id]
        context.inherited_memory = history  # Treat loaded as inherited
        context.extra["persistent_conversation_id"] = target_id

        self.conversation_id = target_id
        return True

    def restore_conversation_history(self) -> List[Dict]:
        """
        Restore history from working + episodic memory on startup.
        """
        history = []

        # Try working memory first (recent)
        if self._check_working_memory_health():
            history.extend(self._load_from_working_memory())

        # Then episodic (older)
        if self._check_episodic_health():
            history.extend(self._load_from_episodic(self.conversation_id))

        return history

    # === Helper methods ===
    def _check_episodic_health(self) -> bool: ...
    def _get_episodic_url(self) -> str: ...
    def _get_trace_headers(self) -> Dict: ...
    def _load_from_episodic(self, conv_id: str) -> List[Dict]: ...
    def _load_from_working_memory(self) -> List[Dict]: ...
```

**Pros:**
- Single source of truth for conversation operations
- OZOLITH logging automatic for all operations
- Clear ownership

**Cons:**
- Orchestrator becomes bigger (more responsibilities)
- Mixes session management with persistence concerns
- Needs service_manager dependency

---

## OPTION B: Separate ConversationManager (lives with episodic)

**Philosophy:** Orchestrator = session/sidebars. Manager = persistence.

```python
# conversation_manager.py (NEW FILE)

class ConversationManager:
    """
    Handles conversation persistence to/from episodic memory.
    Uses ConversationOrchestrator for session tracking + OZOLITH.
    """

    def __init__(self, service_manager, orchestrator: ConversationOrchestrator):
        self.service_manager = service_manager
        self.orchestrator = orchestrator
        self.conversation_id: Optional[str] = None

    def start_new_conversation(self, task_description: str = None) -> str:
        """Start fresh conversation."""
        # Persistent ID
        self.conversation_id = str(uuid.uuid4())

        # Tell orchestrator (handles in-memory + OZOLITH)
        context_id = self.orchestrator.create_root_context(
            task_description=task_description
        )

        return context_id

    def list_conversations(self) -> List[Dict]:
        """List past conversations from episodic memory."""
        if not self._check_episodic_health():
            return []

        response = requests.get(
            f"{self._get_episodic_url()}/recent?limit=50",
            timeout=5
        )
        return response.json().get('conversations', []) if response.ok else []

    def switch_conversation(self, target_id: str) -> bool:
        """Switch to different conversation."""
        history = self._load_from_episodic(target_id)
        if not history:
            return False

        # Create context via orchestrator
        context_id = self.orchestrator.create_root_context(
            task_description=f"Resumed: {target_id[:8]}..."
        )

        # Load history into context
        context = self.orchestrator.get_context(context_id)
        context.inherited_memory = history

        self.conversation_id = target_id
        return True

    def store_exchange(self, user_msg: str, assistant_msg: str, metadata: Dict = None):
        """
        Store exchange - both to memory services AND orchestrator.
        """
        context_id = self.orchestrator.get_active_context_id()

        # Store via orchestrator (in-memory + OZOLITH)
        exchange_id = self.orchestrator.add_exchange(
            context_id, user_msg, assistant_msg, metadata
        )

        # ALSO persist to working memory service
        self._persist_to_working_memory(exchange_id, user_msg, assistant_msg)

        return exchange_id

    def restore_conversation_history(self) -> List[Dict]:
        """Restore from working + episodic memory."""
        # ... same as Option A

    # === Episodic memory client methods ===
    def _check_episodic_health(self) -> bool: ...
    def _get_episodic_url(self) -> str: ...
    def _load_from_episodic(self, conv_id: str) -> List[Dict]: ...
    def _persist_to_working_memory(self, ...): ...
```

**Then rich_chat.py becomes:**
```python
class RichMemoryChat:
    def __init__(self, ...):
        # Create orchestrator
        self.orchestrator = get_orchestrator(error_handler=self.error_handler)

        # Create manager (uses orchestrator)
        self.conversation_manager = ConversationManager(
            service_manager=self.service_manager,
            orchestrator=self.orchestrator
        )

    def start_new_conversation(self):
        # Delegate
        context_id = self.conversation_manager.start_new_conversation()
        self.ui_handler.show_new_conversation_panel(context_id)

    def list_conversations(self):
        # Delegate + display
        conversations = self.conversation_manager.list_conversations()
        self.ui_handler.show_conversation_list(conversations)
```

**Pros:**
- Clear separation of concerns
- Orchestrator stays focused (session/sidebar/OZOLITH)
- Manager handles persistence (episodic memory client)
- Easier to test each independently

**Cons:**
- Two objects to coordinate
- Have to pass orchestrator into manager
- Slightly more complex wiring

---

## OPTION C: Manager IN episodic_memory_coordinator.py

**Philosophy:** Persistence code lives with persistence layer.

```python
# episodic_memory_coordinator.py (expanded)

class EpisodicMemoryCoordinator:
    """
    Existing: Coordinates with episodic memory service
    NEW: Also handles conversation lifecycle
    """

    # Existing methods...

    # NEW: Conversation management
    def list_conversations(self, limit: int = 50) -> List[Dict]: ...
    def load_conversation(self, conv_id: str) -> List[Dict]: ...
    def start_new_conversation(self) -> str: ...  # Just generates ID
```

**Then rich_chat.py or ConversationManager uses it:**
```python
# Coordinator handles episodic API
conversations = self.episodic_coordinator.list_conversations()

# Orchestrator handles session + OZOLITH
context_id = self.orchestrator.create_root_context()
```

**Pros:**
- All episodic memory stuff in one place
- Coordinator already exists and handles that service

**Cons:**
- Doesn't naturally integrate with OZOLITH
- Still need orchestrator for session tracking
- Two places to coordinate

---

## My Recommendation

**Option B (Separate ConversationManager)** because:

1. **Clear responsibilities:**
   - Orchestrator = session state + sidebars + OZOLITH
   - Manager = persistence + episodic memory client

2. **OZOLITH integration is clean:**
   - Manager calls orchestrator methods → OZOLITH logging happens automatically
   - No duplicate logging logic

3. **Testable:**
   - Can test manager with mock orchestrator
   - Can test orchestrator without episodic memory

4. **Matches the extraction goal:**
   - Pull conversation code out of rich_chat.py
   - Put it in dedicated module
   - Wire to orchestrator for session/OZOLITH

---

## Questions to Resolve

1. Does Manager live in `conversation_manager.py` (new) or inside `episodic_memory_coordinator.py` (existing)?

2. Should Manager own `conversation_id` or should Orchestrator?

3. How much UI display code stays in rich_chat.py vs moves to Manager?

---

**Next Step:** Pick an option and I'll implement it.
