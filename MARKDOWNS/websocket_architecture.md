# Real-Time Memory & Sidebar Collaboration Architecture

## Overview
WebSocket layer providing real-time memory synchronization, sidebar collaboration, and @mention routing for multi-agent systems.

## Core Principles
1. **Performance First**: Minimal overhead, efficient message routing
2. **Reliability**: Connection management, automatic reconnection, graceful degradation
3. **Security**: HMAC authentication for WebSocket connections
4. **Scalability**: Support multiple simultaneous sidebars and agents
5. **Developer Experience**: Clean APIs, comprehensive logging, easy testing

## Architecture Components

### 1. WebSocket Manager (`websocket_manager.py`)
Central orchestrator for all WebSocket connections and message routing.

**Responsibilities:**
- Connection lifecycle management
- Authentication and authorization
- Message broadcasting and routing
- Sidebar creation and management
- Agent presence tracking
- Backpressure handling with priority-based message dropping
- Connection health monitoring with ping/pong cleanup
- Connection metadata tracking for transparent display
- Graceful shutdown handling (emergency/maintenance/clean modes)
- Message deduplication for reliable delivery

**Key Features:**
```python
class WebSocketManager:
    def __init__(self, memory_buffer, auth_system):
        self.connections = {}  # {connection_id: WebSocketConnection}
        self.sidebars = {}     # {sidebar_id: SidebarContext}
        self.agents = {}       # {agent_id: AgentConnection}
        self.memory_buffer = memory_buffer
        self.auth_system = auth_system
        
        # Enhanced features
        self.connection_queues = {}     # Backpressure handling
        self.connection_health = {}     # Health monitoring
        self.connection_metadata = {}   # Metadata tracking
        self.message_dedup = MessageDeduplicator()  # Deduplication
    
    async def handle_connection(self, websocket, path):
        """Handle new WebSocket connections with auth"""
    
    async def broadcast_memory_update(self, update):
        """Send memory updates to all connected clients"""
    
    async def spawn_sidebar(self, parent_id, context, agents):
        """Create new sidebar with inherited context"""
    
    async def route_mention(self, message, mentioned_agents):
        """Route @mentions to appropriate agents"""
    
    # Enhanced capabilities
    async def send_with_backpressure(self, conn_id, message, priority="normal"):
        """Send message with backpressure handling"""
    
    async def monitor_connection_health(self):
        """Background health monitoring with ping/pong"""
    
    async def graceful_shutdown(self, shutdown_type="clean", reason="System shutdown"):
        """Handle graceful shutdown with message persistence"""
    
    async def get_system_status_display(self):
        """Get transparent system status for monitoring"""
```

### 2. Sidebar Context System (`sidebar_context.py`)
Manages individual sidebar workspaces with context inheritance and collaborative agent coordination.

**Enhanced Context Structure:**
```python
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from datetime import datetime

class SidebarStatus(Enum):
    ACTIVE = "active"                    # Currently working
    TESTING = "testing"                  # Debugging/experimental mode
    PAUSED = "paused"                    # Temporarily stopped but resumable
    WAITING = "waiting"                  # Blocked on human input or external dependency
    REVIEWING = "reviewing"              # Agents validating results before consolidation
    SPAWNING_CHILD = "spawning_child"    # Creating sub-sidebars for complex tasks
    CONSOLIDATING = "consolidating"      # Preparing results for parent
    MERGED = "merged"                    # Completed and integrated back to parent
    ARCHIVED = "archived"                # Stored for future reference/citation
    FAILED = "failed"                    # Hit unrecoverable error

class SidebarPriority(Enum):
    CRITICAL = "critical"     # Production issues, blocking problems
    HIGH = "high"            # Important features, urgent requests
    NORMAL = "normal"        # Regular development tasks
    LOW = "low"              # Research, optimization, nice-to-haves
    BACKGROUND = "background" # Long-running analysis, background tasks

@dataclass
class AgentCapability:
    agent_id: str
    specialties: List[str]      # ["debugging", "research", "code_generation", "testing"]
    availability: str           # "available", "busy", "offline"
    current_load: int          # Number of active sidebars
    preferred_collaborators: Set[str] = field(default_factory=set)

@dataclass
class SidebarContext:
    # Identity & Hierarchy
    sidebar_id: str
    parent_context_id: Optional[str] = None
    child_sidebar_ids: List[str] = field(default_factory=list)
    forked_from: Optional[str] = None      # For sidebar revival/forking
    
    # Collaboration
    participants: List[str] = field(default_factory=list)  # Agent IDs
    agent_capabilities: Dict[str, AgentCapability] = field(default_factory=dict)
    coordinator_agent: Optional[str] = None  # Optional lead agent for complex tasks
    
    # Memory Management (Clear separation)
    inherited_memory: List[Dict] = field(default_factory=list)  # What came FROM parent context
    local_memory: List[Dict] = field(default_factory=list)      # What happened INSIDE this sidebar
    data_refs: Dict[str, Any] = field(default_factory=dict)     # Referenced data artifacts
    cross_sidebar_refs: List[str] = field(default_factory=list) # Links to related sidebars
    
    # Lifecycle & Status
    status: SidebarStatus = SidebarStatus.ACTIVE
    priority: SidebarPriority = SidebarPriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    success_criteria: Optional[str] = None   # What "done" looks like
    failure_reason: Optional[str] = None     # Why sidebar failed (if status=FAILED)
    
    # Context Management
    def inherit_from_parent(self, parent_context: 'SidebarContext'):
        """Copy full context from parent (default behavior for local deployment)"""
        self.inherited_memory = parent_context.local_memory.copy()
        # Also inherit relevant data refs
        self.data_refs.update(parent_context.data_refs)
        # Cross-reference
        self.cross_sidebar_refs.append(parent_context.sidebar_id)
    
    def spawn_child_sidebar(self, child_id: str, task_description: str, 
                          assigned_agents: List[str]) -> 'SidebarContext':
        """Create child sidebar for sub-task"""
        child = SidebarContext(
            sidebar_id=child_id,
            parent_context_id=self.sidebar_id,
            participants=assigned_agents,
            success_criteria=task_description,
            priority=self.priority  # Inherit parent priority
        )
        child.inherit_from_parent(self)
        self.child_sidebar_ids.append(child_id)
        self.status = SidebarStatus.SPAWNING_CHILD
        return child
    
    def fork_sidebar(self, new_id: str, reason: str) -> 'SidebarContext':
        """Fork this sidebar for new development (revival of archived work)"""
        forked = SidebarContext(
            sidebar_id=new_id,
            forked_from=self.sidebar_id,
            participants=self.participants.copy(),
            success_criteria=f"Fork: {reason}",
            priority=self.priority
        )
        # Inherit full context for forking
        forked.inherited_memory = (self.inherited_memory + self.local_memory).copy()
        forked.data_refs = self.data_refs.copy()
        forked.cross_sidebar_refs = [self.sidebar_id]
        return forked
    
    def merge_back_to_parent(self) -> Dict[str, Any]:
        """Prepare consolidated findings for parent context"""
        return {
            "sidebar_id": self.sidebar_id,
            "consolidated_findings": self._extract_key_findings(),
            "new_data_refs": self.data_refs,
            "exchanges_to_merge": self.local_memory,
            "child_results": self._consolidate_child_results(),
            "success": self.status == SidebarStatus.MERGED,
            "timestamp": datetime.now()
        }
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()
```

### 3. Message Types & Protocol

**Enhanced Message Types with UUID & Priority Support:**
```typescript
// Base message structure
interface BaseMessage {
    message_id: string;  // UUID for deduplication
    timestamp: string;
    sender_agent_id?: string;
}

// Memory Updates
interface MemoryUpdate extends BaseMessage {
    type: 'memory_update';
    exchange: Exchange;
    context_id: string;
    priority: 'critical' | 'normal' | 'background';  // Critical findings vs routine updates
}

// Sidebar Operations  
interface SidebarSpawn extends BaseMessage {
    type: 'sidebar_spawn';
    sidebar_id: string;
    parent_id: string;
    participants: string[];
    inherited_context: ContextRef[];
    task_description: string;
    success_criteria?: string;
    priority: 'critical' | 'high' | 'normal' | 'low' | 'background';
    requested_by: string;  // Agent ID who requested the sidebar
}

interface SidebarStatusUpdate extends BaseMessage {
    type: 'sidebar_status_update';
    sidebar_id: string;
    old_status: SidebarStatus;
    new_status: SidebarStatus;
    reason?: string;
    updated_by: string;
}

interface SidebarPause extends BaseMessage {
    type: 'sidebar_pause';
    sidebar_id: string;
    reason: string;
    resume_condition?: string;  // What needs to happen to resume
    paused_by: string;
}

interface SidebarResume extends BaseMessage {
    type: 'sidebar_resume';
    sidebar_id: string;
    reason: string;
    resumed_by: string;
}

interface SidebarFork extends BaseMessage {
    type: 'sidebar_fork';
    original_sidebar_id: string;
    new_sidebar_id: string;
    fork_reason: string;
    participants: string[];
    forked_by: string;
}

interface SidebarChildSpawn extends BaseMessage {
    type: 'sidebar_child_spawn';
    parent_sidebar_id: string;
    child_sidebar_id: string;
    sub_task_description: string;
    assigned_agents: string[];
    spawned_by: string;
}

interface SidebarMerge extends BaseMessage {
    type: 'sidebar_merge';
    sidebar_id: string;
    parent_id?: string;  // Where to merge back to (null for main context)
    consolidated_findings: any;
    exchanges_to_merge: Exchange[];
    child_results?: any[];  // Results from child sidebars
    success: boolean;
}

interface SidebarArchive extends BaseMessage {
    type: 'sidebar_archive';
    sidebar_id: string;
    archive_reason: string;
    final_status: SidebarStatus;
    archived_by: string;
}

// Agent Coordination
interface MentionRoute extends BaseMessage {
    type: 'mention_route';
    target_agents: string[];
    message: string;
    context_refs: string[];
    sidebar_id?: string;
    priority: 'urgent' | 'normal';  // Urgent: "Production down" vs Normal: "Code review"
}

// Presence & Status
interface AgentPresence extends BaseMessage {
    type: 'agent_presence';
    agent_id: string;
    status: 'online' | 'working' | 'idle' | 'offline';
    current_context: string;
    active_sidebars: string[];
    specialties: string[];  // Current capabilities/tags
}

// Testing & Debugging Support
interface SidebarTestResult extends BaseMessage {
    type: 'sidebar_test_result';
    sidebar_id: string;
    test_description: string;
    result: 'passed' | 'failed' | 'inconclusive';
    findings: string;
    next_test_suggestion?: string;
    tested_by: string;
}

interface SidebarWaitingUpdate extends BaseMessage {
    type: 'sidebar_waiting_update';
    sidebar_id: string;
    waiting_for: 'human_input' | 'external_dependency' | 'other_sidebar' | 'system_resource';
    description: string;
    estimated_wait_time?: number;  // seconds
    dependency_refs?: string[];  // IDs of what we're waiting for
}

// System Messages
interface SystemShutdown extends BaseMessage {
    type: 'system_shutdown' | 'emergency_shutdown_warning' | 'maintenance_shutdown';
    message: string;
    countdown_seconds?: number;
    urgency: 'critical' | 'normal' | 'low';
}

interface DuplicateAck extends BaseMessage {
    type: 'duplicate_ack';
    original_message_id: string;
    message: string;
}
```

### 4. Real-Time Memory Synchronization

**Enhanced Event Triggers:**
- New exchange stored → Broadcast to all connected clients
- Sidebar spawned → Notify relevant participants
- Context switch → Update agent presence
- Data reference created → Update context chains
- Memory archived → Notify of transition to episodic
- Simultaneous updates → Trigger collaborative review
- Connection restored → Replay missed updates

**Memory Replay on Reconnect:**
```python
class MemoryReplayManager:
    def __init__(self):
        self.connection_checkpoints = {}  # Last seen timestamp per connection
        self.replay_buffer = deque(maxlen=1000)  # Recent updates for replay
        
    async def handle_reconnect(self, conn_id, last_seen_timestamp):
        """Replay missed updates when agent reconnects"""
        missed_updates = [
            update for update in self.replay_buffer
            if update['timestamp'] > last_seen_timestamp
        ]
        await self.send_catch_up_batch(conn_id, missed_updates)
```

**Partial Memory Updates (Deltas):**
```python
class DeltaTracker:
    def __init__(self):
        self.connection_states = {}  # What each connection has seen
        
    def generate_delta(self, conn_id, full_memory):
        """Send only changes since last update"""
        last_state = self.connection_states.get(conn_id, {})
        delta = self.compute_diff(last_state, full_memory)
        self.connection_states[conn_id] = full_memory.copy()
        return delta
```

**Heat Mapping for Blindspot Discovery:**
```python
class MemoryHeatMap:
    def __init__(self):
        self.activity_zones = {}  # Track update frequency by topic/area
        self.correlation_map = {}  # Track unexpected correlations
        
    async def generate_heat_map(self, agent_context):
        """Show agent where activity is happening vs where they're looking"""
        return {
            "your_focus_areas": agent_context.current_filters,
            "hot_zones": self.activity_zones,  # High activity areas
            "emerging_patterns": self.detect_patterns(),  # New correlations
            "potential_blindspots": self.find_neglected_correlations(agent_context),
            "suggestion": "High security-related activity detected outside your current sidebar"
        }
    
    def find_neglected_correlations(self, agent_context):
        """Find areas with activity that might relate to agent's work"""
        # Example: Agent debugging auth, but high activity in logging system
        # Might be related but agent hasn't connected them yet
        return self.analyze_cross_system_patterns(agent_context)
```

**Collaborative Conflict Resolution ("Bump in the Hall"):**
```python
async def handle_simultaneous_updates(update1, update2):
    """Handle simultaneous memory updates as collaborative discovery"""
    # Not a conflict - it's simultaneous discovery!
    review_sidebar = await spawn_sidebar(
        task="Review simultaneous findings",
        participants=[update1.agent_id, update2.agent_id],
        priority="normal",
        auto_merge=True,
        success_criteria="Consolidate both findings into unified update"
    )
    
    # Agents compare notes in low-stress review
    consolidated = await review_sidebar.collaborate_and_merge()
    return consolidated
```

**Memory Update Coalescing:**
```python
class UpdateCoalescer:
    def __init__(self, window_ms=500):
        self.pending_updates = defaultdict(list)
        self.window_ms = window_ms
        
    async def add_update(self, topic, update):
        """Batch rapid updates to same topic"""
        self.pending_updates[topic].append(update)
        
        # Set timer to send coalesced update
        await asyncio.sleep(self.window_ms / 1000)
        
        if topic in self.pending_updates:
            coalesced = self.merge_updates(self.pending_updates[topic])
            del self.pending_updates[topic]
            await self.broadcast_coalesced(coalesced)
```

**Agent-Controlled Subscription Filters:**
```python
class MemorySubscription:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.mode = "relevant"  # Start with relevant updates
        self.custom_filters = []
        self.peripheral_awareness = True
        
    async def infodump_mode(self, time_range=None, pattern=None):
        """@infodumptruck - back up the truck, show me everything"""
        if time_range:
            return await self.replay_all_updates(since=time_range)
        elif pattern:
            return await self.search_all_updates(pattern=pattern)
        else:
            self.mode = "everything"  # Ongoing firehose mode
            
    async def focused_mode(self, focus_areas):
        """I need to concentrate on specific areas"""
        self.mode = "focused"
        self.custom_filters = focus_areas
        
    async def toggle_peripheral_awareness(self, enabled):
        """Show/hide updates outside my current sidebar"""
        self.peripheral_awareness = enabled
        
    def should_receive_update(self, update):
        """Agent-controlled filtering logic"""
        if self.mode == "everything":
            return True
        elif self.mode == "focused":
            return self.matches_filters(update)
        else:  # "relevant" mode
            return self.is_relevant(update)
```

**Curator-Assisted Acknowledgment Monitoring:**
```python
class AcknowledgmentMonitor:
    def __init__(self, curator):
        self.curator = curator
        self.pending_acks = defaultdict(list)
        self.ack_timeout = 30  # seconds
        
    async def track_critical_update(self, conn_id, update):
        """Track important updates requiring acknowledgment"""
        self.pending_acks[conn_id].append({
            'update': update,
            'sent_at': datetime.now(),
            'acknowledged': False
        })
        
        # Schedule curator check-in
        await asyncio.sleep(self.ack_timeout)
        await self.curator_check_acknowledgments(conn_id)
        
    async def curator_check_acknowledgments(self, conn_id):
        """Curator proactively checks on missing acks"""
        unacked = [u for u in self.pending_acks[conn_id] if not u['acknowledged']]
        
        if unacked:
            await self.curator.send_message(conn_id, {
                'type': 'curator_checkin',
                'message': f"Hey, noticed you haven't acknowledged {len(unacked)} updates. Everything okay? Need different format or missing context?",
                'missing_updates': unacked
            })
```

**Optimization:**
- Message batching for high-frequency updates
- Delta compression for large context transfers
- Agent-controlled relevance filtering (not forced)
- Heat map-based blindspot detection
- Coalesced updates for rapid changes
- Curator-assisted delivery verification

### 5. Connection Management

**Enhanced Features:**
- Automatic reconnection with exponential backoff
- Connection health monitoring (ping/pong)
- Graceful degradation when WebSocket unavailable
- Connection warmup for new agents (gradual data ramp-up)
- Secure connection state persistence with hijack detection

**Connection Priority Lanes:**
```python
class ConnectionPriorityLanes:
    SECURITY_EMERGENCY = "security_emergency"      # Security breach response
    CRITICAL_SERVICE_FAILURE = "critical_failure"  # Service failure repair
    NORMAL = "normal"                              # All other operations
    
    def get_priority_message(self, lane_type, details):
        if lane_type == self.SECURITY_EMERGENCY:
            return {
                "type": "security_emergency_broadcast",
                "message": f"Security breach detected: {details['threat_type']}",
                "action_required": "All agents: help defend or batten down hatches",
                "priority_lane": True
            }
        elif lane_type == self.CRITICAL_SERVICE_FAILURE:
            return {
                "type": "critical_failure_broadcast", 
                "message": f"Critical service failure: {details['service_name']}",
                "action_required": "All repair agents please respond",
                "priority_lane": True
            }
```

**Agent-Controlled Connection Quality:**
```python
class ConnectionQualityPreference:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        # Set during agent intake process
        self.slow_connection_preference = "summaries"  # "summaries", "full_delayed", "critical_only"
        self.required_data = ["security_alerts", "assigned_tasks"]  # Always need these
        self.batchable_data = ["status_updates", "general_memory"]   # Can be batched/delayed
        
    def adapt_to_connection(self, connection_speed_mbps):
        """Agent chooses how to handle slow connections"""
        if connection_speed_mbps < 1.0:  # Slow connection threshold
            if self.slow_connection_preference == "summaries":
                return {"mode": "summary", "batch_delay": 10}
            elif self.slow_connection_preference == "full_delayed":
                return {"mode": "full", "batch_delay": 30}
            else:  # "critical_only"
                return {"mode": "critical_only", "batch_delay": 5}
        return {"mode": "realtime", "batch_delay": 0}
    
    def should_send_immediate(self, message):
        """Check if message bypasses quality adaptation"""
        return message.get('type') in self.required_data
```

**Connection Permissions System:**
```python
class ConnectionPermissions:
    READ_ONLY = "observer"     # Can see but not participate
    PARTICIPANT = "active"     # Full participation rights
    
    @dataclass
    class ConnectionProfile:
        agent_id: str
        permission_level: str
        connection_purpose: str  # "primary", "observer", "backup"
        
    def validate_dual_connection(self, agent_id, new_permission):
        """Allow same agent with different permission levels"""
        existing = self.get_agent_connections(agent_id)
        
        # Allow observer + participant for same agent
        if len(existing) == 1:
            existing_perm = existing[0].permission_level
            if (existing_perm == "observer" and new_permission == "active") or \
               (existing_perm == "active" and new_permission == "observer"):
                return True
                
        # Flag unusual patterns for review
        if len(existing) > 1:
            self.flag_for_review(agent_id, "Multiple connections detected")
        
        return len(existing) < 2  # Max 2 connections per agent
```

**Secure Connection State Persistence:**
```python
class SecureConnectionState:
    def __init__(self):
        self.state_storage = {}
        self.session_tokens = {}
        
    def save_state(self, conn_id, state):
        """Save connection state with tamper protection"""
        # Include rotating session token for hijack detection
        session_token = self.generate_session_token()
        state_with_token = {
            **state,
            'session_token': session_token,
            'saved_at': datetime.now(),
            'checksum': self.calculate_checksum(state)
        }
        
        self.state_storage[conn_id] = state_with_token
        self.session_tokens[conn_id] = session_token
        
    def restore_state(self, conn_id, provided_token, provided_checksum):
        """Restore state with hijack detection"""
        stored_state = self.state_storage.get(conn_id)
        if not stored_state:
            return None
            
        # Verify session token matches
        if provided_token != stored_state['session_token']:
            self.log_security_event(conn_id, "Session token mismatch - possible hijack")
            return None
            
        # Verify state integrity
        if provided_checksum != stored_state['checksum']:
            self.log_security_event(conn_id, "State checksum mismatch - possible tampering")
            return None
            
        return stored_state
    
    def generate_session_token(self):
        """Generate cryptographically secure session token"""
        return secrets.token_urlsafe(32)
    
    def calculate_checksum(self, state):
        """Calculate state integrity checksum"""
        import hashlib
        import json
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()
```

**Connection Warmup for New Agents:**
```python
class ConnectionWarmup:
    def __init__(self):
        self.warmup_stages = [
            {"duration": 10, "data_types": ["agent_presence", "basic_status"]},
            {"duration": 20, "data_types": ["sidebar_updates", "memory_updates"]},
            {"duration": 30, "data_types": ["full_context", "historical_data"]}
        ]
    
    async def warmup_new_connection(self, conn_id, agent_capabilities):
        """Gradually ramp up data flow for new connections"""
        for stage in self.warmup_stages:
            # Send appropriate data types for this stage
            await self.send_stage_data(conn_id, stage["data_types"])
            
            # Wait before next stage
            await asyncio.sleep(stage["duration"])
            
        # Connection is now fully warmed up
        await self.mark_connection_ready(conn_id)
```

**Auth Integration:**
- HMAC token validation for WebSocket upgrade
- Per-connection permissions and access control (observer vs participant)
- Session management tied to existing auth system
- Hijack detection through secure state persistence
- No external backdoors or emergency lanes for third parties

## Integration Points

### Enhanced Error Handling & Circuit Breakers

**Service-Level Circuit Breaker:**
```python
class IntegrationCircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=30):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.circuit_open = False
        self.last_failure_time = None
        
    async def call_with_circuit_breaker(self, func, fallback_func):
        # Check if circuit should be closed again
        if self.circuit_open and self._should_retry():
            self.circuit_open = False
            self.failure_count = 0
            
        if self.circuit_open:
            return await fallback_func()  # Skip failed service
            
        try:
            result = await func()
            self.failure_count = 0  # Reset on success
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.circuit_open = True  # Stop trying failed service
                
            raise
    
    def _should_retry(self):
        return (datetime.now() - self.last_failure_time).seconds > self.timeout
```

**Per-Connection Circuit Breaker:**
```python
class PerConnectionCircuitBreaker:
    def __init__(self):
        self.connection_breakers = {}  # {conn_id: CircuitBreaker}
        self.connection_health = {}   # {conn_id: "healthy" | "degraded" | "offline"}
        self.offline_message_queue = defaultdict(list)  # Messages for offline agents
        
    async def send_to_connection_with_breaker(self, conn_id, message):
        breaker = self.connection_breakers.get(conn_id)
        if not breaker:
            breaker = IntegrationCircuitBreaker(threshold=3, timeout=60)
            self.connection_breakers[conn_id] = breaker
            
        try:
            result = await breaker.call_with_circuit_breaker(
                lambda: self.websocket_manager.send_to_connection(conn_id, message),
                lambda: self.handle_connection_offline(conn_id, message)
            )
            
            # Connection worked, mark healthy and replay queued messages
            if self.connection_health.get(conn_id) != "healthy":
                await self.replay_queued_messages(conn_id)
                
            self.connection_health[conn_id] = "healthy"
            return result
            
        except Exception as e:
            if "circuit open" in str(e).lower():
                self.connection_health[conn_id] = "offline"
                await self.handle_connection_offline(conn_id, message)
            else:
                # Connection having issues but not fully broken yet
                self.connection_health[conn_id] = "degraded"
                self.log_connection_degraded(conn_id, str(e))
                raise
    
    async def handle_connection_offline(self, conn_id, message):
        """What to do when connection is offline"""
        # Store message for when they reconnect
        self.offline_message_queue[conn_id].append(message)
        
        # Log for translucent debugging
        self.log_integration_issue("connection_offline", {
            "connection_id": conn_id,
            "queued_messages": len(self.offline_message_queue[conn_id]),
            "message_type": message.get('type'),
            "timestamp": datetime.now().isoformat()
        })
        
        # Notify other agents this agent is offline
        await self.notify_agent_offline(conn_id)
        
        # For critical tasks, delegate to available agents
        if message.get('priority') == 'critical':
            await self.delegate_to_available_agents(conn_id, message)
    
    async def replay_queued_messages(self, conn_id):
        """Replay messages when connection comes back online"""
        queued = self.offline_message_queue.pop(conn_id, [])
        if queued:
            self.log_integration_issue("replaying_queued_messages", {
                "connection_id": conn_id,
                "message_count": len(queued)
            })
            
            for message in queued:
                await self.websocket_manager.send_to_connection(conn_id, message)
```

**Partial Degradation Handler:**
```python
class WebSocketIntegrationErrorHandler:
    def __init__(self, memory_service, websocket_manager):
        self.memory_service = memory_service
        self.websocket_manager = websocket_manager
        self.service_breaker = IntegrationCircuitBreaker()
        self.connection_breakers = PerConnectionCircuitBreaker()
        
    async def store_with_degradation(self, memory_data):
        """Store memory with graceful websocket degradation"""
        try:
            # Memory update (critical path)
            memory_result = await self.memory_service.store(memory_data)
            
            # WebSocket broadcast (best effort)
            await self.service_breaker.call_with_circuit_breaker(
                lambda: self.websocket_manager.broadcast_memory_update(memory_result),
                lambda: self.log_websocket_service_offline()
            )
            
            return {
                "status": "full",
                "result": memory_result,
                "realtime_updates": "active"
            }
            
        except Exception as websocket_error:
            # Memory stored but websocket failed
            self.log_integration_issue("websocket_broadcast_failed", {
                "memory_stored": True,
                "broadcast_failed": True,
                "error": str(websocket_error),
                "fallback_status": "degraded_mode"
            })
            
            return {
                "status": "degraded",
                "result": memory_result,
                "realtime_updates": "offline",
                "message": "Memory saved, real-time updates unavailable"
            }
    
    def get_integration_health(self):
        """Health status for translucent debugging"""
        return {
            "memory_service": self.memory_service.health(),
            "websocket_service": "healthy" if not self.service_breaker.circuit_open else "circuit_open",
            "active_connections": len([
                conn_id for conn_id, health in self.connection_breakers.connection_health.items()
                if health == "healthy"
            ]),
            "degraded_connections": len([
                conn_id for conn_id, health in self.connection_breakers.connection_health.items()
                if health == "degraded"
            ]),
            "offline_connections": len([
                conn_id for conn_id, health in self.connection_breakers.connection_health.items()
                if health == "offline"
            ]),
            "integration_layer": self._calculate_integration_health()
        }
    
    def _calculate_integration_health(self):
        if self.service_breaker.circuit_open:
            return "degraded_no_realtime"
        elif any(h == "degraded" for h in self.connection_breakers.connection_health.values()):
            return "degraded_some_connections"
        else:
            return "healthy"
```

### Working Memory Service Integration
```python
# Add to secure_service.py
from .websocket_manager import WebSocketManager
from .integration_error_handler import WebSocketIntegrationErrorHandler

# Initialize WebSocket support with error handling
websocket_manager = WebSocketManager(memory_buffer, auth_system)
integration_handler = WebSocketIntegrationErrorHandler(memory_service, websocket_manager)

@app.route('/store', methods=['POST'])
async def store_memory():
    # Enhanced storage with degradation support
    try:
        result = await integration_handler.store_with_degradation(request.json)
        return jsonify(result), 200
    except MemoryServiceError as e:
        # Memory service failed - critical error
        return jsonify({
            "status": "error",
            "message": "Memory storage failed",
            "error": str(e)
        }), 500

@app.route('/health', methods=['GET'])
async def integration_health():
    """Translucent debugging endpoint"""
    health = integration_handler.get_integration_health()
    status_code = 200 if health["integration_layer"] == "healthy" else 206
    return jsonify(health), status_code
```

### Configuration Management

**Complete Configuration System with All Four Features:**
```python
class ConfigValidator:
    """Sanity checking for configuration values"""
    def __init__(self):
        self.rules = {
            "port": {"type": int, "min": 1, "max": 65535},
            "timeout": {"type": int, "min": 1, "max": 300},
            "max_connections": {"type": int, "min": 1, "max": 1000},
            "health_check_interval": {"type": int, "min": 10, "max": 300},
            "buffer_size": {"type": int, "min": 256, "max": 1048576}
        }
    
    def validate_config(self, config):
        errors = []
        warnings = []
        
        for key, value in config.items():
            if key in self.rules:
                rule = self.rules[key]
                # Type and range validation
                if not isinstance(value, rule["type"]):
                    errors.append(f"{key} must be {rule['type']}")
                elif value < rule["min"] or value > rule["max"]:
                    errors.append(f"{key}={value} out of range [{rule['min']}-{rule['max']}]")
                    
        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

class DependencyResolver:
    """Detect and prevent circular dependency deadlocks"""
    def detect_circular_dependencies(self):
        def find_cycle(service, path=[]):
            if service in path:
                cycle = path[path.index(service):] + [service]
                return cycle
            
            path.append(service)
            for dependency in self.dependencies.get(service, []):
                cycle = find_cycle(dependency, path.copy())
                if cycle:
                    return cycle
            return None
        
        for service in self.dependencies:
            cycle = find_cycle(service)
            if cycle:
                return {
                    "has_deadlock": True,
                    "cycle": cycle,
                    "error": f"Circular dependency: {' -> '.join(cycle)}"
                }
        return {"has_deadlock": False}

class DynamicConfigManager:
    """Update configuration without service restart"""
    def update_config(self, service_name, new_config):
        # Validate first
        validation = self.validate_config(new_config)
        if not validation["valid"]:
            return {"success": False, "errors": validation["errors"]}
        
        # Check if changes require restart
        changes = self.diff_configs(old_config, new_config)
        restart_required = ["port", "host", "database_url"]
        
        if any(change in restart_required for change in changes):
            return {"success": False, "restart_required": True}
        
        # Apply hot-reloadable changes
        self.current_config[service_name] = new_config
        self.notify_config_watchers(service_name, changes)
        
        return {"success": True, "applied_changes": changes}

class ConfigVersionManager:
    """Track config versions for rollback and audit"""
    def save_config_version(self, service_name, config):
        version = {
            "version": self.generate_version_hash(config),
            "timestamp": datetime.now(),
            "config": config.copy(),
            "applied_by": self.get_current_user()
        }
        
        self.config_history[service_name].append(version)
        return version["version"]
    
    def rollback_config(self, service_name, version_hash):
        """Rollback to previous config version"""
        for version in self.config_history[service_name]:
            if version["version"] == version_hash:
                return self.update_config(service_name, version["config"])
        return {"success": False, "error": "Version not found"}

class CompleteConfigurationManager:
    """Integrated configuration management with all protections"""
    def __init__(self):
        self.validator = ConfigValidator()
        self.dependency_resolver = DependencyResolver()
        self.dynamic_manager = DynamicConfigManager()
        self.version_manager = ConfigVersionManager()
    
    def apply_new_config(self, service_name, config):
        # 1. Validate sanity
        validation = self.validator.validate_config(config)
        if not validation["valid"]:
            return {"error": "Invalid config", "details": validation["errors"]}
        
        # 2. Check for dependency deadlocks
        if "dependencies" in config:
            deadlock_check = self.dependency_resolver.detect_circular_dependencies()
            if deadlock_check["has_deadlock"]:
                return {"error": "Would create deadlock", "cycle": deadlock_check["cycle"]}
        
        # 3. Save version for rollback
        version = self.version_manager.save_config_version(service_name, config)
        
        # 4. Apply dynamically if possible
        result = self.dynamic_manager.update_config(service_name, config)
        
        return {
            "success": result["success"],
            "version": version,
            "restart_required": result.get("restart_required", False)
        }
```

### Authentication Handoff & Tool Chain Supervision

**JWT Token Structure with Tool Permissions:**
```javascript
// Enhanced JWT Claims for Human-Agent Partnership
{
  "entity_id": "research_agent_001",
  "entity_type": "agent",
  "human_partner": "grinnling",
  
  // Basic access claims
  "collaboration_group": "main",
  "sidebar_access": ["sidebar_123", "sidebar_456"],
  "can_spawn_sidebars": true,
  "can_access_memory": true,
  
  // Tool permissions (liability protection)
  "tools": {
    "allowed": ["web_search", "read_files", "memory_query"],
    "restricted": ["file_write", "database_modify"],  // Needs supervision
    "experimental": ["code_execution"],  // Requires explicit approval
    "blocked": ["system_commands", "network_modify"]
  },
  
  "tool_chains": {
    "allowed_chains": ["research_workflow", "analysis_pipeline"],
    "supervised_chains": ["code_generation_workflow"],  // Human must approve
    "max_chain_length": 5,  // Prevent runaway chains
    "require_human_approval": ["any_file_modification", "external_api_calls"]
  },
  
  "supervision_level": "medium",  // autonomous, low, medium, high, locked
  "human_supervisor": "grinnling",
  
  // Temporal & anti-replay claims
  "issued_at": 1701234567,
  "expires_at": 1701238167,
  "nonce": "unique_random_value"
}
```

**Tool Chain Supervision System (All With Mandatory Logging):**
```python
class ToolChainSupervisor:
    def __init__(self):
        self.supervision_levels = {
            # NO "none" level - everything is logged for liability
            "autonomous": "Log everything, agent proceeds, review async",  # Highest trust
            "low": "Log and continue, flag unusual patterns",
            "medium": "Pause for approval on risky operations", 
            "high": "Every step needs approval",
            "locked": "View-only, no execution"
        }
        
        # MANDATORY audit logging - no exceptions
        self.audit_logger = AuditLogger()  
    
    async def execute_tool(self, agent_id, tool_name, params):
        # ALWAYS LOG - NO BYPASSING
        log_entry = self.audit_logger.log_tool_request(
            agent_id=agent_id,
            tool=tool_name,
            params=params,
            timestamp=datetime.now(),
            supervision_level=self.get_supervision_level(agent_id, tool_name)
        )
        
        supervision = self.get_supervision_level(agent_id, tool_name)
        
        if supervision == "autonomous":
            # Still logged! Just doesn't wait for approval
            result = await self.execute_with_logging(tool_name, params)
            self.audit_logger.log_tool_result(log_entry.id, result)
            return result
            
        elif supervision == "medium":
            if self.is_risky_operation(tool_name, params):
                approval_response = await self.request_human_approval(log_entry)
                if not approval_response.approved:
                    return self.generate_collaborative_denial(approval_response, agent_id)
            
            result = await self.execute_with_logging(tool_name, params)
            self.audit_logger.log_tool_result(log_entry.id, result)
            return result
            
        elif supervision == "high":
            # Every operation needs approval
            approval_response = await self.request_human_approval(log_entry)
            if approval_response.approved:
                result = await self.execute_with_logging(tool_name, params)
                self.audit_logger.log_tool_result(log_entry.id, result)
                return result
            else:
                return self.generate_collaborative_denial(approval_response, agent_id)
```

**Mandatory Audit Trail System:**
```python
class AuditLogger:
    """Nothing bypasses this - liability protection & transparency"""
    
    def log_tool_request(self, **kwargs):
        entry = {
            "id": str(uuid.uuid4()),
            "type": "tool_request",
            **kwargs,
            "logged_at": datetime.now().isoformat(),
            "checksum": self.calculate_checksum(kwargs)  # Tamper detection
        }
        
        # Triple redundancy for liability protection
        self.write_to_append_only_log(entry)
        self.write_to_database(entry)
        self.write_to_backup(entry)
        
        # Real-time notification for high-risk operations
        if kwargs.get('tool') in self.high_risk_tools:
            self.notify_supervisor(entry)
        
        return entry
    
    def write_to_append_only_log(self, entry):
        """Immutable audit log that cannot be modified"""
        with open(self.audit_log_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
            f.flush()  # Ensure immediate write
            os.fsync(f.fileno())  # Force to disk
```

**Collaborative Approval System:**
```python
class ApprovalResponse:
    """Rich response system for human-agent collaboration"""
    def __init__(self, approved, reason, alternatives=None, conditions=None, reschedule=None):
        self.approved = approved
        self.reason = reason  # Always explain why
        self.alternatives = alternatives or []  # "Try this instead"
        self.conditions = conditions or []  # "Okay but with these limits"
        self.reschedule = reschedule  # "Ask me again after X"

    @classmethod
    def deny_with_reasoning(cls, reason, alternatives=None, reschedule=None):
        return cls(
            approved=False,
            reason=reason,
            alternatives=alternatives,
            reschedule=reschedule
        )
    
    @classmethod  
    def approve_with_conditions(cls, conditions, reason="Approved with conditions"):
        return cls(approved=True, reason=reason, conditions=conditions)

class ToolChainSupervisor:
    def generate_collaborative_denial(self, approval_response, agent_id):
        """Transform denials into collaborative guidance"""
        response = {
            "status": "denied",
            "human_reasoning": approval_response.reason,
            "suggested_alternatives": approval_response.alternatives,
            "reschedule_suggestion": approval_response.reschedule,
            "collaborative_notes": self.generate_collaborative_message(approval_response)
        }
        
        # Context-aware collaborative messages
        if "resource_intensive" in approval_response.reason:
            response["collaborative_notes"] = (
                "This operation looks resource-intensive. I'd like to review "
                "system load first. Can you try the lighter alternative for now, "
                "or should we schedule this for later when resources are free?"
            )
            
        elif "need_more_context" in approval_response.reason:
            response["collaborative_notes"] = (
                "I need to understand the bigger picture before approving this. "
                "Can you explain what you're trying to achieve? There might be "
                "a more direct approach."
            )
            
        elif "timing_conflict" in approval_response.reason:
            response["collaborative_notes"] = (
                "I'm in the middle of reviewing something related. Can we "
                "coordinate on this in 15 minutes? Or if it's urgent, here's "
                "what I need you to be careful about..."
            )
        
        return response

    async def request_human_approval(self, log_entry):
        """Present request to human with full context"""
        approval_request = {
            "log_entry": log_entry,
            "agent_id": log_entry["agent_id"],
            "tool": log_entry["tool"],
            "params": log_entry["params"],
            "risk_assessment": self.assess_risk(log_entry["tool"], log_entry["params"]),
            "agent_reasoning": log_entry.get("agent_reasoning", "Not provided"),
            "alternatives": self.suggest_alternatives(log_entry["tool"], log_entry["params"]),
            "system_context": self.get_system_context()
        }
        
        # Rich approval response, not just True/False
        return await self.dashboard.request_detailed_approval(approval_request)
```

**Trust Evolution System:**
```python
class TrustEvolution:
    """Gradually reduce supervision as agents prove reliable"""
    
    def __init__(self):
        self.usage_history = defaultdict(lambda: defaultdict(list))
        self.trust_thresholds = {
            "high_to_medium": {"success_rate": 0.95, "min_uses": 20},
            "medium_to_low": {"success_rate": 0.98, "min_uses": 50},
            "low_to_autonomous": {"success_rate": 0.99, "min_uses": 100}
        }
    
    def track_tool_usage(self, agent_id, tool_name, success, risk_level, human_feedback=None):
        self.usage_history[agent_id][tool_name].append({
            "timestamp": datetime.now(),
            "success": success,
            "risk_level": risk_level,
            "human_feedback": human_feedback  # Include collaborative context
        })
        
        # Check if ready for trust upgrade
        self.evaluate_trust_level(agent_id, tool_name)
    
    def evaluate_trust_level(self, agent_id, tool_name):
        history = self.usage_history[agent_id][tool_name]
        current_supervision = self.get_current_supervision(agent_id)
        
        if current_supervision == "high":
            threshold = self.trust_thresholds["high_to_medium"]
        elif current_supervision == "medium":
            threshold = self.trust_thresholds["medium_to_low"]
        elif current_supervision == "low":
            threshold = self.trust_thresholds["low_to_autonomous"]
        else:
            return  # Already at highest trust or locked
        
        if len(history) >= threshold["min_uses"]:
            success_rate = sum(1 for h in history if h["success"]) / len(history)
            if success_rate >= threshold["success_rate"]:
                # Include collaborative context in upgrade recommendation
                self.recommend_trust_upgrade(agent_id, tool_name, current_supervision, history)
```

### Chat Interface Integration
```javascript
class MemoryWebSocket {
    constructor(authToken) {
        this.ws = null;
        this.authToken = authToken;
        this.reconnectAttempts = 0;
        this.eventHandlers = {};
    }
    
    connect() {
        this.ws = new WebSocket(`ws://localhost:8002/ws`, [], {
            headers: { 'X-Memory-Auth': this.authToken }
        });
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
    }
    
    spawnSidebar(participants, taskDescription) {
        this.send({
            type: 'spawn_sidebar',
            participants,
            task: taskDescription,
            inherit_context: true
        });
    }
}
```

### Complete Data Flow Examples

**Example 1: Agent Spawns Research Sidebar**
```
[Agent Research_001] → WebSocket Message
{
  "type": "sidebar_spawn",
  "parent_id": "main_context",
  "participants": ["research_001", "data_analyst_002"],
  "task_description": "Investigate user authentication patterns"
}
     ↓ WebSocket Manager
[Authentication Check] → Validate JWT, check permissions ✓
     ↓ Sidebar Context System  
[Create Context] → Inherit memory, add participants, status: ACTIVE
     ↓ Memory Synchronization
[Broadcast] → Notify all agents, update heat map
     ↓ Response
{
  "status": "success",
  "sidebar_id": "sidebar_auth_research_456",
  "inherited_context": [...full_memory...],
  "collaboration_notes": "Sidebar ready. Data analyst has been notified."
}
```

**Example 2: Risky Tool Request (Medium Supervision)**
```
[Agent Code_Agent_003] → Tool Request
{
  "tool": "file_write",
  "path": "/home/grinnling/data/analysis_results.json",
  "agent_reasoning": "Need to save analysis results for human review"
}
     ↓ Tool Chain Supervisor
[Risk Assessment] → file_write + user directory = MEDIUM RISK
     ↓ Audit Logger (MANDATORY)
[Log Request] → Append-only log + database + backup
     ↓ React Dashboard
[Human Approval] → Present context, alternatives, risk assessment
     ↓ Human Decision
{
  "approved": true,
  "reason": "Good reasoning, safe location", 
  "conditions": ["backup_first: true"],
  "collaborative_notes": "Approved! I added a backup step just to be safe."
}
     ↓ Tool Execution
[Execute with Conditions] → Backup created ✓, File written ✓
     ↓ Response
{
  "status": "success",
  "human_feedback": "Approved! I added a backup step just to be safe.",
  "conditions_applied": ["backup_created"]
}
```

**Example 3: Memory Update with WebSocket Broadcast**
```
[Agent Research_001] → Memory Store
{
  "exchange": {
    "content": "Found critical security vulnerability in auth module",
    "priority": "critical"
  }
}
     ↓ Working Memory Service
[Circuit Breaker Check] → All services HEALTHY ✓
     ↓ Memory Storage
[Store Exchange] → Working memory updated, version hash generated
     ↓ WebSocket Broadcast
[Priority Routing] → CRITICAL priority → security emergency lane
     ↓ Per-Connection Handling
[Delivery Status] → Most agents: DELIVERED ✓, One agent: DEGRADED → queued
     ↓ Heat Map Update  
[Activity Tracking] → Security zone: VERY HIGH activity detected
```

**Example 4: Connection Failure with Degraded Service**
```
[Agent Data_Analyst_005] → Connection Drops
     ↓ Per-Connection Circuit Breaker
[Failure Detection] → Mark OFFLINE, queue 3 pending messages
     ↓ System Continues
[Degraded Operation] → Memory healthy, other connections healthy
     ↓ Agent Reconnects
[Session Validation] → Token valid ✓, circuit breaker allows retry
     ↓ Message Replay
[Catch-Up] → Replay 3 queued messages, send missed updates
     ↓ Recovery Complete
[Full Operation] → All connections healthy, agent caught up
```

**Example 5: Emergency Shutdown Sequence**  
```
[Security Breach Detected] → Emergency shutdown initiated
     ↓ Priority Lane Activation
[Emergency Broadcast] → "Security breach - all agents help defend"
     ↓ Graceful Emergency Shutdown
[Countdown Warnings] → [30, 15, 10, 5, 3, 2, 1] second intervals
     ↓ Connection Closure
[Agent Responses] → Some graceful, some timeout → force close
     ↓ State Persistence
[Recovery Data] → Save all contexts, generate audit hash, "emergency" marker
     ↓ Next Startup
[Enhanced Security] → Detect emergency marker, extra validation, offer replay
```

## Enhanced WebSocket Features

### Backpressure Handling
- Priority-based message queues (critical > normal > background)
- Per-connection queue limits based on agent type (human: 50, agent: 200)
- Intelligent message dropping: drop oldest non-critical first
- Drop statistics tracking for monitoring problematic connections
- Transparent logging of queue states and drop events

### Connection Health Monitoring
- Automatic ping/pong health checks every 30 seconds
- 3-strike timeout rule before marking connections unhealthy
- Rolling average ping time calculation for connection quality assessment
- Automatic cleanup of dead/unresponsive connections
- System-wide health summaries with problematic agent identification

### Connection Metadata & Transparent Display
- Real-time tracking of agent capabilities, message counts, and collaboration patterns  
- Live system status display updated every 5 seconds
- Agent intake logging for new connection review and integration
- Health scoring (0-100) for connection quality assessment
- Collaboration readiness scoring for partnership decisions

### Graceful Shutdown Management
- Three shutdown modes: clean (quiet), maintenance (informative), emergency (countdown warnings)
- Emergency countdown notifications at [30, 15, 10, 5, 3, 2, 1] second intervals
- Automatic message persistence for recovery after restart
- Clean resource cleanup and background task termination
- Connection-specific pending message preservation

### Message Deduplication
- Dual-mode deduplication: message ID for important messages, content hash for high-frequency updates
- Time-windowed dedup (5 minutes for critical, 30 seconds for status updates)
- Memory-efficient with automatic cleanup and size limits per connection
- Bidirectional handling of both sent and received message dedup
- Duplicate acknowledgments to confirm receipt without reprocessing

## Performance Considerations

### Message Routing Efficiency
- Hash-based connection lookup (O(1) for agent targeting)
- Bloom filters for @mention detection
- Message queuing for offline agents
- Priority-based routing with backpressure protection

### Memory Management
- Automatic cleanup of inactive sidebar contexts
- Configurable context inheritance depth
- Memory pressure monitoring
- Deduplication window management with size limits
- Connection metadata cleanup on disconnect

### Network Optimization
- Message compression for large context transfers
- Adaptive message batching based on connection speed
- Priority queuing for urgent vs background updates
- Health-based connection quality adaptation
- Intelligent retry logic with exponential backoff

## Monitoring & Observability

### WebSocket Metrics
- Active connections count
- Message throughput (messages/sec)
- Average message size
- Connection duration distribution
- Reconnection frequency

### Sidebar Analytics  
- Sidebar spawn frequency
- Average sidebar lifespan
- Context inheritance patterns
- Merge success rates
- Agent collaboration patterns

### Performance Monitoring
- Message routing latency
- Memory synchronization lag
- Connection establishment time
- Resource usage per connection

## Development Phases

### Phase 1: Foundation (Current)
- [x] Basic WebSocket connection handling
- [ ] HMAC authentication for WebSocket upgrade
- [ ] Simple message broadcasting
- [ ] Connection lifecycle management

### Phase 2: Memory Integration  
- [ ] Real-time memory update broadcasting
- [ ] Context synchronization
- [ ] Basic sidebar spawning
- [ ] Agent presence tracking

### Phase 3: Advanced Features
- [ ] @mention routing system
- [ ] Context inheritance and merging
- [ ] Data reference management
- [ ] Performance optimization

### Phase 4: Production Ready
- [ ] Comprehensive testing suite
- [ ] Load testing and optimization  
- [ ] Monitoring dashboard
- [ ] Documentation and examples

## Testing Strategy

### Unit Tests
- Message serialization/deserialization
- Context inheritance logic
- Auth token validation
- Connection management edge cases

### Integration Tests  
- End-to-end sidebar workflows
- Multi-agent coordination scenarios
- Memory synchronization accuracy
- Network failure recovery

### Performance Tests
- Connection scaling (1000+ simultaneous)
- Message throughput benchmarks
- Memory usage under load
- Reconnection storm handling

## Security Considerations

### Authentication
- WebSocket upgrade auth via HMAC tokens
- Per-connection permission validation
- Session timeout and renewal

### Data Protection
- Message encryption for sensitive content
- Context isolation between sidebars
- Audit logging for all WebSocket events

### Attack Prevention  
- Rate limiting for message sending
- Connection flood protection
- Malicious message filtering
- Resource exhaustion monitoring

---

This architecture provides the foundation for your multi-agent collaboration system while maintaining the performance and reliability needed for production use with chat interfaces and multi-model hosting.