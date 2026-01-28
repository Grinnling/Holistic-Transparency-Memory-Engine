# Phase 2 & 3 Implementation Guide
## Enhanced Intelligence Features for Claude

---

## 🎯 **Implementation Order & Time Estimates**

### **Phase 1: Core (Already Built)**
✅ Basic chat interface
✅ Error collection
✅ Service monitoring
✅ File upload UI

### **Phase 2: Enhanced Intelligence (~2 hours total)**
🔧 Message ↔ Error Linking (30 min)
🔧 Memory Query Visibility (1 hour)
🔧 Basic trend tracking (30 min)

### **Phase 3: Advanced Analytics (~2 hours total)**
📊 Confidence trend visualization (1 hour)
📊 Service health history (1 hour)

---

## 📊 **Phase 2.1: Message ↔ Error Linking**
**Time: 30 minutes**
**Impact: HIGH - Helps Claude understand error patterns**

### **Backend Implementation**

```python
# api_server.py - Enhanced error tracking

# Add to ChatResponse model
class ChatResponse(BaseModel):
    response: str
    confidence_score: float = None
    operation_context: str = None
    error: str = None
    message_id: str = None  # NEW: Unique message ID

# Update track_error function
def track_error(
    error: str, 
    operation_context: str = None,
    service: str = None, 
    severity: str = "normal",
    triggering_message_id: str = None,  # NEW
    conversation_state: dict = None      # NEW
):
    """Track errors with message context"""
    
    # Get last 3 messages for context
    related_messages = []
    if chat.conversation_history:
        related_messages = [
            exchange.get('message_id') 
            for exchange in chat.conversation_history[-3:]
            if exchange.get('message_id')
        ]
    
    # Build conversation state snapshot
    if not conversation_state:
        conversation_state = {
            'message_count': len(chat.conversation_history),
            'average_confidence': calculate_average_confidence(),
            'active_services': get_active_services()
        }
    
    error_event = ErrorEvent(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        error=error,
        operation_context=operation_context,
        service=service,
        severity=severity,
        triggering_message_id=triggering_message_id,
        related_messages=related_messages,
        conversation_state=conversation_state
    )
    
    # ... rest of existing code

# Update chat endpoint to include message IDs
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(message: ChatMessage):
    message_id = str(uuid.uuid4())  # Generate ID
    
    try:
        result = chat.process_message(message.message)
        
        # Store message ID in conversation history
        if chat.conversation_history:
            chat.conversation_history[-1]['message_id'] = message_id
        
        response = ChatResponse(
            response=result.get('response', 'No response generated'),
            confidence_score=result.get('validation', {}).get('confidence_score'),
            operation_context=f"chat_message: {message.message[:50]}...",
            message_id=message_id  # Include in response
        )
        
        return response
        
    except Exception as e:
        track_error(
            str(e),
            f"chat_message: {message.message[:50]}...",
            "chat_processor",
            "critical",
            triggering_message_id=message_id  # Link error to message
        )
        raise

# Helper functions
def calculate_average_confidence():
    """Calculate average confidence of last 10 messages"""
    if not chat.conversation_history:
        return 0.0
    
    recent = chat.conversation_history[-10:]
    confidences = [
        ex.get('validation', {}).get('confidence_score', 0.0)
        for ex in recent
    ]
    return sum(confidences) / len(confidences) if confidences else 0.0

def get_active_services():
    """Get list of currently healthy services"""
    return [
        service for service, data in serviceStatus.items()
        if data.get('status') == 'healthy'
    ]
```

### **Frontend Implementation**

```typescript
// components/ErrorPanel.tsx - Add message context display

// Add to ErrorPanel component state
const [messageMap, setMessageMap] = useState<Map<string, ChatMessage>>(new Map());

// Helper to get message by ID
const getMessageById = (messageId: string): ChatMessage | undefined => {
  return messageMap.get(messageId);
};

// Update parent component to pass messages
interface ErrorPanelProps {
  errors: ErrorEvent[];
  messages: ChatMessage[];  // NEW: Pass all messages
  onAcknowledge: (errorId: string) => void;
  onClear: () => void;
  onReportFix: (errorId: string, worked: boolean) => void;
}

// Build message map on mount/update
useEffect(() => {
  const map = new Map();
  messages.forEach(msg => {
    if (msg.id) map.set(msg.id, msg);
  });
  setMessageMap(map);
}, [messages]);

// Add to error display (inside error.map loop)
{error.triggering_message_id && (
  <div className="mt-2 p-2 bg-gray-50 rounded border-l-2 border-blue-500">
    <div className="text-xs font-medium text-gray-700 mb-1">
      Triggered by message:
    </div>
    <div className="text-xs text-gray-600 font-mono">
      {(() => {
        const msg = getMessageById(error.triggering_message_id);
        return msg ? msg.content.substring(0, 100) + '...' : 'Message not found';
      })()}
    </div>
    <div className="text-xs text-gray-500 mt-1">
      Message ID: {error.triggering_message_id.substring(0, 8)}...
    </div>
  </div>
)}

{error.related_messages && error.related_messages.length > 0 && (
  <details className="mt-2">
    <summary className="text-xs text-gray-600 cursor-pointer hover:text-gray-800">
      📝 View conversation context ({error.related_messages.length} messages)
    </summary>
    <div className="mt-2 space-y-1 ml-2 pl-2 border-l-2 border-gray-300">
      {error.related_messages.map((msgId, i) => {
        const msg = getMessageById(msgId);
        return (
          <div key={i} className="text-xs">
            <span className="text-gray-500 font-mono">
              {msg ? `${msg.role}: ${msg.content.substring(0, 80)}...` : 'Message not available'}
            </span>
          </div>
        );
      })}
    </div>
  </details>
)}

{error.conversation_state && (
  <div className="mt-2 text-xs text-gray-500 font-mono bg-gray-50 p-2 rounded">
    <div>Messages: {error.conversation_state.message_count}</div>
    <div>Avg Confidence: {Math.round(error.conversation_state.average_confidence * 100)}%</div>
    <div>Active Services: {error.conversation_state.active_services?.join(', ')}</div>
  </div>
)}
```

### **Testing Checklist**
- [ ] Each message gets unique ID
- [ ] Errors link to triggering message
- [ ] Can expand to see last 3 messages
- [ ] Conversation state snapshot captured
- [ ] Message context shows in error panel

---

## 🔍 **Phase 2.2: Memory Query Visibility**
**Time: 1 hour**
**Impact: HIGH - Helps Claude see memory system performance**

### **Backend Implementation**

```python
# api_server.py - Memory query tracking

# Add memory query tracking
memory_queries = []  # Store last 50 queries

async def track_memory_query(
    query: str,
    results: list,
    message_id: str,
    query_type: str,
    search_time_ms: float,
    reformulated_query: str = None
):
    """Track and broadcast memory queries"""
    
    query_event = {
        'id': str(uuid.uuid4()),
        'type': 'memory_query',
        'timestamp': datetime.now().isoformat(),
        'query': query,
        'results_found': len(results),
        'relevance_scores': [r.get('score', 0.0) for r in results[:5]],
        'search_time_ms': search_time_ms,
        'message_id': message_id,
        'query_type': query_type,
        'reformulated_query': reformulated_query,
        'source': 'terminal'
    }
    
    # Store locally
    memory_queries.append(query_event)
    memory_queries[:] = memory_queries[-50:]  # Keep last 50
    
    # Broadcast to React
    await broadcast_to_react(query_event)

# Add endpoint to get memory query history
@app.get("/memory/queries")
async def get_memory_queries():
    """Get recent memory queries"""
    return {"queries": memory_queries}

# Integrate with existing memory calls
# (This is pseudocode - adapt to your rich_chat.py structure)
@app.post("/chat")
async def chat_endpoint(message: ChatMessage):
    message_id = str(uuid.uuid4())
    
    try:
        # Before processing message, hook into memory system
        start_time = time.time()
        
        # Your existing memory recall
        memories = await recall_from_memory(message.message)
        
        search_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Track the query
        await track_memory_query(
            query=message.message,
            results=memories,
            message_id=message_id,
            query_type='episodic',  # or 'working', 'semantic'
            search_time_ms=search_time
        )
        
        # Continue with regular processing...
        
    except Exception as e:
        # ... error handling
```

### **Frontend Implementation**

```typescript
// components/MemoryActivityPanel.tsx - NEW COMPONENT

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';
import { Search, Clock, Target, TrendingUp } from 'lucide-react';

interface MemoryQuery {
  id: string;
  timestamp: string;
  query: string;
  results_found: number;
  relevance_scores: number[];
  search_time_ms: number;
  message_id: string;
  query_type: 'episodic' | 'working' | 'semantic';
  reformulated_query?: string;
}

interface MemoryActivityPanelProps {
  queries: MemoryQuery[];
  onQueryClick?: (query: MemoryQuery) => void;
}

const MemoryActivityPanel: React.FC<MemoryActivityPanelProps> = ({ 
  queries,
  onQueryClick 
}) => {
  
  const [filter, setFilter] = useState<'all' | 'episodic' | 'working' | 'semantic'>('all');
  
  const filteredQueries = queries.filter(q => 
    filter === 'all' || q.query_type === filter
  );
  
  const avgSearchTime = queries.length > 0
    ? queries.reduce((sum, q) => sum + q.search_time_ms, 0) / queries.length
    : 0;
    
  const avgResults = queries.length > 0
    ? queries.reduce((sum, q) => sum + q.results_found, 0) / queries.length
    : 0;

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Search className="h-4 w-4" />
          Memory Activity
        </CardTitle>
        
        {/* Stats */}
        <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
          <div className="flex items-center gap-1">
            <Clock className="h-3 w-3 text-gray-400" />
            <span className="text-gray-600">Avg:</span>
            <span className="font-medium">{avgSearchTime.toFixed(0)}ms</span>
          </div>
          <div className="flex items-center gap-1">
            <Target className="h-3 w-3 text-gray-400" />
            <span className="text-gray-600">Results:</span>
            <span className="font-medium">{avgResults.toFixed(1)}</span>
          </div>
        </div>
        
        {/* Filters */}
        <div className="flex gap-1 mt-2">
          {['all', 'episodic', 'working', 'semantic'].map(f => (
            <Button
              key={f}
              size="sm"
              variant={filter === f ? "default" : "outline"}
              onClick={() => setFilter(f as any)}
              className="text-xs"
            >
              {f}
            </Button>
          ))}
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-hidden">
        <ScrollArea className="h-full">
          {filteredQueries.length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              No memory queries yet
            </div>
          ) : (
            <div className="space-y-2">
              {filteredQueries.map(query => (
                <div
                  key={query.id}
                  className="border-l-2 border-blue-500 pl-3 pb-3 cursor-pointer hover:bg-gray-50 rounded"
                  onClick={() => onQueryClick?.(query)}
                >
                  {/* Query text */}
                  <div className="text-sm font-medium mb-1">
                    {query.query.substring(0, 100)}
                    {query.query.length > 100 && '...'}
                  </div>
                  
                  {/* Reformulated query if different */}
                  {query.reformulated_query && query.reformulated_query !== query.query && (
                    <div className="text-xs text-gray-600 mb-1">
                      🔄 Reformulated: {query.reformulated_query.substring(0, 80)}...
                    </div>
                  )}
                  
                  {/* Metadata */}
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <Badge variant="outline" className="text-xs">
                      {query.query_type}
                    </Badge>
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {query.search_time_ms.toFixed(0)}ms
                    </span>
                    <span>{query.results_found} results</span>
                    <span className="ml-auto">
                      {new Date(query.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  
                  {/* Relevance scores visualization */}
                  {query.relevance_scores.length > 0 && (
                    <div className="flex gap-0.5 mt-2">
                      {query.relevance_scores.map((score, i) => (
                        <div
                          key={i}
                          className="h-2 flex-1 bg-blue-500 rounded"
                          style={{ opacity: score }}
                          title={`Result ${i + 1}: ${Math.round(score * 100)}% relevant`}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
};

export default MemoryActivityPanel;
```

### **Integrate into App.tsx**

```typescript
// Add to App.tsx

// Import new component
import MemoryActivityPanel from './components/MemoryActivityPanel';

// Add state
const [memoryQueries, setMemoryQueries] = useState<MemoryQuery[]>([]);

// Load on mount
useEffect(() => {
  loadMemoryQueries();
}, []);

const loadMemoryQueries = async () => {
  try {
    const response = await fetch(`${API_BASE}/memory/queries`);
    if (response.ok) {
      const data = await response.json();
      setMemoryQueries(data.queries || []);
    }
  } catch (error) {
    console.error('Failed to load memory queries:', error);
  }
};

// Handle WebSocket updates
const handleWebSocketMessage = (data: any) => {
  switch (data.type) {
    // ... existing cases
    
    case 'memory_query':
      setMemoryQueries(prev => [...prev, data].slice(-50)); // Keep last 50
      break;
  }
};

// Add new tab in sidebar
<TabsList className="m-4 mb-2 w-full grid grid-cols-3">
  <TabsTrigger value="status">Status</TabsTrigger>
  <TabsTrigger value="errors">Errors</TabsTrigger>
  <TabsTrigger value="memory">Memory</TabsTrigger>  {/* NEW */}
</TabsList>

<TabsContent value="memory" className="h-full m-4 mt-2">
  <MemoryActivityPanel 
    queries={memoryQueries}
    onQueryClick={(query) => {
      // Optional: scroll to message that triggered this query
      const message = messages.find(m => m.id === query.message_id);
      if (message) {
        console.log('Query triggered by:', message);
      }
    }}
  />
</TabsContent>
```

### **Testing Checklist**
- [ ] Memory queries appear in real-time
- [ ] Shows search time for each query
- [ ] Relevance scores visualized
- [ ] Can filter by query type
- [ ] Links to messages that triggered queries
- [ ] Reformulated queries displayed

---

## 📈 **Phase 3.1: Confidence Trend Visualization**
**Time: 1 hour**
**Impact: MEDIUM - Helps Claude spot degradation**

### **Backend Implementation**

```python
# api_server.py - Confidence tracking

class ConfidenceTracker:
    def __init__(self):
        self.history = []
        self.topic_scores = defaultdict(list)  # Track by topic
    
    def add_response(self, confidence: float, content: str = None):
        """Add confidence score and analyze trends"""
        self.history.append({
            'confidence': confidence,
            'timestamp': datetime.now().isoformat()
        })
        
        # Extract topic (simple keyword extraction)
        if content:
            # TODO: Better topic detection
            topics = extract_keywords(content)
            for topic in topics:
                self.topic_scores[topic].append(confidence)
        
        # Broadcast trend if we have enough data
        if len(self.history) >= 10:
            asyncio.create_task(self.broadcast_trend())
    
    async def broadcast_trend(self):
        """Calculate and broadcast confidence trend"""
        last_10 = self.history[-10:]
        last_20 = self.history[-20:] if len(self.history) >= 20 else self.history
        
        current_avg = sum(h['confidence'] for h in last_10) / len(last_10)
        overall_avg = sum(h['confidence'] for h in last_20) / len(last_20)
        
        # Detect trend direction
        first_half = sum(h['confidence'] for h in last_10[:5]) / 5
        second_half = sum(h['confidence'] for h in last_10[5:]) / 5
        
        trend = 'stable'
        if second_half > first_half + 0.1:
            trend = 'improving'
        elif second_half < first_half - 0.1:
            trend = 'degrading'
        
        # Find low confidence topics
        low_confidence_topics = [
            topic for topic, scores in self.topic_scores.items()
            if len(scores) >= 3 and sum(scores)/len(scores) < 0.7
        ]
        
        await broadcast_to_react({
            'type': 'confidence_trend',
            'conversation_id': chat.conversation_id,
            'current_average': current_avg,
            'last_10_average': current_avg,
            'overall_average': overall_avg,
            'trend': trend,
            'low_confidence_topics': low_confidence_topics[:5],
            'history': [h['confidence'] for h in last_20],
            'timestamp': datetime.now().isoformat()
        })

# Initialize tracker
confidence_tracker = ConfidenceTracker()

# Update chat endpoint
@app.post("/chat")
async def chat_endpoint(message: ChatMessage):
    # ... existing code ...
    
    # Track confidence
    if result.get('validation', {}).get('confidence_score'):
        confidence_tracker.add_response(
            result['validation']['confidence_score'],
            message.message
        )
    
    return response
```

### **Frontend Implementation**

Add to ServiceStatusPanel.tsx:

```typescript
// In ServiceStatusPanel.tsx - add confidence trend card

interface ConfidenceTrend {
  current_average: number;
  trend: 'improving' | 'degrading' | 'stable';
  low_confidence_topics?: string[];
  history: number[];
}

interface ServiceStatusPanelProps {
  services: ServiceStatus;
  conversationId: string;
  confidenceTrend?: ConfidenceTrend;  // NEW
  onToggleService?: (service: string, action: 'start' | 'stop' | 'restart') => void;
}

// Add confidence trend card
{confidenceTrend && (
  <Card>
    <CardHeader className="pb-3">
      <div className="flex items-center justify-between">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <TrendingUp className="h-4 w-4" />
          Confidence Trend
        </CardTitle>
        <Badge 
          variant={
            confidenceTrend.trend === 'degrading' ? 'destructive' :
            confidenceTrend.trend === 'improving' ? 'default' :
            'secondary'
          }
        >
          {confidenceTrend.trend}
        </Badge>
      </div>
    </CardHeader>
    
    <CardContent>
      {/* Current average */}
      <div className="text-3xl font-bold">
        {Math.round(confidenceTrend.current_average * 100)}%
      </div>
      <div className="text-xs text-gray-500 mb-3">
        Average over last 10 responses
      </div>
      
      {/* Sparkline */}
      <div className="flex items-end gap-0.5 h-12 mb-3">
        {confidenceTrend.history.map((score, i) => (
          <div
            key={i}
            className={`flex-1 rounded-t transition-all ${
              score >= 0.8 ? 'bg-green-500' :
              score >= 0.6 ? 'bg-yellow-500' :
              'bg-red-500'
            }`}
            style={{ height: `${score * 100}%` }}
            title={`${Math.round(score * 100)}%`}
          />
        ))}
      </div>
      
      {/* Low confidence topics */}
      {confidenceTrend.low_confidence_topics && confidenceTrend.low_confidence_topics.length > 0 && (
        <div className="mt-3 pt-3 border-t">
          <div className="text-xs font-medium text-gray-700 mb-2">
            Topics needing attention:
          </div>
          <div className="flex flex-wrap gap-1">
            {confidenceTrend.low_confidence_topics.map(topic => (
              <Badge key={topic} variant="outline" className="text-xs">
                {topic}
              </Badge>
            ))}
          </div>
        </div>
      )}
      
      {/* Alert for degrading trend */}
      {confidenceTrend.trend === 'degrading' && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">
          ⚠️ Response confidence is declining. Consider:
          <ul className="ml-4 mt-1 space-y-0.5">
            <li>• Checking service health</li>
            <li>• Reviewing recent queries</li>
            <li>• Simplifying questions</li>
          </ul>
        </div>
      )}
    </CardContent>
  </Card>
)}
```

### **Testing Checklist**
- [ ] Confidence trend updates after 10 messages
- [ ] Sparkline shows last 20 scores
- [ ] Color coding (green/yellow/red)
- [ ] Trend direction detected
- [ ] Low confidence topics identified
- [ ] Alert shown when degrading

---

## 📊 **Phase 3.2: Service Health History**
**Time: 1 hour**
**Impact: MEDIUM - Identifies chronic issues**

### **Backend Implementation**

```python
# api_server.py - Service health tracking

from collections import defaultdict, deque

class ServiceHealthTracker:
    def __init__(self):
        self.history = defaultdict(lambda: {
            'health_scores': deque(maxlen=20),
            'latencies': deque(maxlen=20),
            'error_counts': deque(maxlen=20),
            'status_changes': deque(maxlen=10),
            'last_status': None
        })
    
    def record_check(self, service: str, is_healthy: bool, 
                    latency: float = None, errors: int = 0):
        """Record health check result"""
        hist = self.history[service]
        
        # Add to history
        hist['health_scores'].append(100 if is_healthy else 0)
        if latency:
            hist['latencies'].append(latency)
        hist['error_counts'].append(errors)
        
        # Detect status change
        current_status = 'healthy' if is_healthy else 'unhealthy'
        if hist['last_status'] and hist['last_status'] != current_status:
            hist['status_changes'].append({
                'timestamp': datetime.now().isoformat(),
                'from_status': hist['last_status'],
                'to_status': current_status
            })
        hist['last_status'] = current_status
        
        # Check for chronic issues
        chronic_issues = self.detect_chronic_issues(service)
        if chronic_issues:
            asyncio.create_task(self.broadcast_health_warning(service, chronic_issues))
    
    def detect_chronic_issues(self, service: str) -> list:
        """Detect patterns indicating chronic problems"""
        hist = self.history[service]
        issues = []
        
        # Check if enough data
        if len(hist['health_scores']) < 10:
            return issues
        
        # Issue 1: High failure rate
        recent_scores = list(hist['health_scores'])[-10:]
        failure_rate = sum(1 for s in recent_scores if s < 50) / len(recent_scores)
        if failure_rate > 0.5:
            issues.append(f"High failure rate ({int(failure_rate * 100)}%)")
        
        # Issue 2: Increasing latency
        if len(hist['latencies']) >= 10:
            latencies = list(hist['latencies'])
            first_half = sum(latencies[:5]) / 5
            second_half = sum(latencies[5:]) / 5
            if second_half > first_half * 1.5:
                issues.append(f"Latency increasing ({int(first_half)}ms → {int(second_half)}ms)")
        
        # Issue 3: Frequent status changes
        if len(hist['status_changes']) >= 5:
            recent_changes = list(hist['status_changes'])[-5:]
            time_window = (
                datetime.fromisoformat(recent_changes[-1]['timestamp']) -
                datetime.fromisoformat(recent_changes[0]['timestamp'])
            ).total_seconds() / 60  # minutes
            
            if time_window < 10:  # 5 changes in < 10 minutes
                issues.append("Frequent status flapping")
        
        return issues
    
    async def broadcast_health_warning(self, service: str, issues: list):
        """Broadcast chronic health issues"""
        await broadcast_to_react({
            'type': 'service_health_warning',
            'service': service,
            'chronic_issues': issues,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_history(self, service: str) -> dict:
        """Get formatted history for service"""
        hist = self.history[service]
        return {
            'service': service,
            'health_scores': list(hist['health_scores']),
            'latencies': list(hist['latencies']),
            'error_counts': list(hist['error_counts']),
            'status_changes': list(hist['status_changes']),
            'chronic_issues': self.detect_chronic_issues(service)
        }

# Initialize tracker
health_tracker = ServiceHealthTracker()

# Update health check
@app.get("/health")
async def health_check():
    health_status = {}
    
    for service in services:
        start_time = time.time()
        is_healthy = chat.check_service_health(service)
        latency = (time.time() - start_time) * 1000
        
        health_status[service] = "healthy" if is_healthy else "unhealthy"
        
        # Record in tracker
        health_tracker.record_check(service, is_healthy, latency)
    
    return health_status

# Add endpoint to get history
@app.get("/health/history/{service}")
async def get_service_history(service: str):
    return health_tracker.get_history(service)
```

### **Frontend Implementation**

Update ServiceStatusPanel.tsx to show history:

```typescript
// Add history display to each service card

{/* Service health history sparkline */}
{serviceHistory && serviceHistory.health_scores.length > 0 && (
  <div className="mt-3 pt-3 border-t">
    <div className="text-xs text-gray-600 mb-2">
      Health History (last 20 checks)
    </div>
    
    {/* Health score sparkline */}
    <div className="flex items-end gap-0.5 h-8 mb-2">
      {serviceHistory.health_scores.map((score, i) => (
        <div
          key={i}
          className={`flex-1 rounded-t transition-all ${
            score > 80 ? 'bg-green-500' :
            score > 50 ? 'bg-yellow-500' :
            'bg-red-500'
          }`}
          style={{ height: `${score}%` }}
          title={`Check ${i + 1}: ${score > 50 ? 'Healthy' : 'Unhealthy'}`}
        />
      ))}
    </div>
    
    {/* Latency trend if available */}
    {serviceHistory.latencies.length > 0 && (
      <>
        <div className="text-xs text-gray-600 mb-2">
          Latency Trend
        </div>
        <div className="flex items-end gap-0.5 h-6">
          {serviceHistory.latencies.map((latency, i) => {
            const maxLatency = Math.max(...serviceHistory.latencies);
            const height = (latency / maxLatency) * 100;
            return (
              <div
                key={i}
                className="flex-1 bg-blue-500 rounded-t"
                style={{ height: `${height}%` }}
                title={`${latency.toFixed(0)}ms`}
              />
            );
          })}
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>{Math.min(...serviceHistory.latencies).toFixed(0)}ms</span>
          <span>{Math.max(...serviceHistory.latencies).toFixed(0)}ms</span>
        </div>
      </>
    )}
    
    {/* Chronic issues warning */}
    {serviceHistory.chronic_issues && serviceHistory.chronic_issues.length > 0 && (
      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded">
        <div className="text-xs font-medium text-red-800 mb-1">
          ⚠️ Chronic Issues Detected:
        </div>
        <ul className="text-xs text-red-700 space-y-0.5">
          {serviceHistory.chronic_issues.map((issue, i) => (
            <li key={i} className="ml-2">• {issue}</li>
          ))}
        </ul>
      </div>
    )}
  </div>
)}
```

### **Testing Checklist**
- [ ] Health history sparkline shows 20 checks
- [ ] Colors indicate health status
- [ ] Latency trend displayed
- [ ] Chronic issues detected and flagged
- [ ] Status change history tracked

---

## 🎯 **Summary: What Each Phase Gives Claude**

### **Phase 2: Enhanced Intelligence**
✅ **Message ↔ Error Linking**
- See what user was asking when error occurred
- Understand conversation context around errors
- Spot patterns: "This question type always fails"

✅ **Memory Query Visibility**
- Watch memory system performance in real-time
- See if queries are reformulated
- Identify slow or unproductive searches
- Suggest memory system improvements

### **Phase 3: Advanced Analytics**
✅ **Confidence Trends**
- Spot degrading response quality early
- Identify topics that need more training
- Correlate confidence with service health

✅ **Service Health History**
- Identify chronic vs transient issues
- See patterns in service failures
- Recommend specific services to restart
- Track if fixes actually work

---

## 📋 **Implementation Priority**

If time-constrained, implement in this order:

1. **Message ↔ Error Linking** (30 min, highest impact)
2. **Memory Query Visibility** (1 hour, second highest)
3. **Confidence Trends** (1 hour, polish)
4. **Service Health History** (1 hour, polish)

Each feature is independent - can be added incrementally!
