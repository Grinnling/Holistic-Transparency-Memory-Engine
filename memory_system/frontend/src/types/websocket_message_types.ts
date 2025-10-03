// websocket_types.ts - Complete message type system
// This defines ALL message types we'll use (now and future)

// Base message interface
interface BaseMessage {
  type: string;
  timestamp: string;
  id: string;
  source: 'terminal' | 'react' | 'system' | 'redis' | 'scratchpad';
}

// === CHAT MESSAGES ===
interface ChatMessage extends BaseMessage {
  type: 'chat_message';
  role: 'user' | 'assistant' | 'system';
  content: string;
  confidence_score?: number;
  operation_context?: string;
  citations?: Citation[];  // Future: source citations
  metadata?: {
    model?: string;
    tokens_used?: number;
    processing_time?: number;
  };
}

interface Citation {
  source: string;
  content: string;
  relevance_score: number;
  type: 'memory' | 'document' | 'web' | 'code' | 'episodic';
}

// === ERROR SYSTEM ===
interface ErrorMessage extends BaseMessage {
  type: 'error_event';
  error: string;
  severity: 'critical' | 'warning' | 'normal' | 'debug';
  operation_context?: string;
  service?: string;
  stack_trace?: string;
  attempted_fixes?: string[];
  fix_success?: boolean;
  user_impact: 'blocking' | 'degraded' | 'minimal' | 'none';
}

interface ErrorResolution extends BaseMessage {
  type: 'error_resolved';
  error_id: string;
  fix_applied: string;
  success: boolean;
  notes?: string;
}

// === SERVICE STATUS ===
interface ServiceStatus extends BaseMessage {
  type: 'service_status';
  services: {
    [serviceName: string]: {
      status: 'healthy' | 'unhealthy' | 'degraded' | 'starting' | 'stopped';
      latency?: number;
      last_check: string;
      error_count?: number;
    };
  };
}

interface ServiceToggle extends BaseMessage {
  type: 'service_toggle';
  service: string;
  action: 'start' | 'stop' | 'restart' | 'enable' | 'disable';
  reason?: string;
}

// === MEMORY & CONTEXT SYSTEM ===
interface MemoryUpdate extends BaseMessage {
  type: 'memory_update';
  operation: 'store' | 'recall' | 'archive' | 'search' | 'restore';
  context_id: string;
  content?: any;
  success: boolean;
  metadata?: {
    confidence_score?: number;
    relevance_score?: number;
    source_service?: string;
  };
}

// === FUTURE: REDIS STREAMING ===
interface RedisStreamMessage extends BaseMessage {
  type: 'redis_stream';
  stream_name: string;
  data: any;
  stream_id: string;
}

interface ScratchpadUpdate extends BaseMessage {
  type: 'scratchpad_update';
  operation: 'create' | 'update' | 'delete' | 'share';
  scratchpad_id: string;
  content?: string;
  sharing_url?: string;
}

// === CONVERSATION MANAGEMENT ===
interface ConversationEvent extends BaseMessage {
  type: 'conversation_created' | 'conversation_switched' | 'conversation_archived';
  conversation_id: string;
  title?: string;
  message_count?: number;
  previous_conversation_id?: string; // For switching
}

// === MULTIMEDIA HANDLING ===
interface MediaEvent extends BaseMessage {
  type: 'media_uploaded' | 'media_processed' | 'media_error';
  media_type: 'video' | 'audio' | 'document' | 'image' | 'code';
  file_path: string;
  file_size?: number;
  processing_status?: 'pending' | 'processing' | 'complete' | 'failed';
  thumbnail_url?: string;
  metadata?: any;
}

// === SYSTEM CONTROL ===
interface SystemControl extends BaseMessage {
  type: 'system_ping' | 'system_pong' | 'system_shutdown' | 'system_restart';
  data?: any;
}

interface ConnectionEvent extends BaseMessage {
  type: 'connection_established' | 'connection_lost' | 'reconnect_attempt';
  client_id: string;
  client_type: 'react' | 'terminal' | 'mobile' | 'api';
  metadata?: {
    user_agent?: string;
    ip_address?: string;
    session_id?: string;
  };
}

// === FUTURE: COLLABORATION ===
interface CollaborationEvent extends BaseMessage {
  type: 'user_joined' | 'user_left' | 'cursor_moved' | 'content_changed';
  user_id: string;
  session_id: string;
  data?: any;
}

// === ANALYTICS & METRICS ===
interface MetricsEvent extends BaseMessage {
  type: 'metrics_update';
  metrics: {
    response_time: number;
    memory_usage: number;
    active_connections: number;
    errors_per_minute: number;
    service_health_score: number;
  };
}

// Union type for all possible messages
type WebSocketMessage = 
  | ChatMessage
  | ErrorMessage 
  | ErrorResolution
  | ServiceStatus
  | ServiceToggle
  | MemoryUpdate
  | RedisStreamMessage
  | ScratchpadUpdate
  | ConversationEvent
  | MediaEvent
  | SystemControl
  | ConnectionEvent
  | CollaborationEvent
  | MetricsEvent;

// Message validation helpers
export const createMessage = <T extends BaseMessage>(
  type: T['type'], 
  data: Omit<T, 'id' | 'timestamp' | 'type'>,
  source: BaseMessage['source'] = 'system'
): T => {
  return {
    type,
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    source,
    ...data
  } as T;
};

// Type guards for message handling
export const isChatMessage = (msg: WebSocketMessage): msg is ChatMessage => 
  msg.type === 'chat_message';

export const isErrorMessage = (msg: WebSocketMessage): msg is ErrorMessage => 
  msg.type === 'error_event';

export const isServiceStatus = (msg: WebSocketMessage): msg is ServiceStatus => 
  msg.type === 'service_status';

// Example usage:
/*
// Creating messages
const chatMsg = createMessage<ChatMessage>('chat_message', {
  role: 'user',
  content: 'Hello world',
  source: 'react'
});

const errorMsg = createMessage<ErrorMessage>('error_event', {
  error: 'Service connection failed',
  severity: 'critical',
  service: 'working_memory',
  operation_context: 'memory_lookup',
  user_impact: 'blocking',
  source: 'terminal'
});

// Handling messages
const handleMessage = (msg: WebSocketMessage) => {
  if (isChatMessage(msg)) {
    // TypeScript knows this is a ChatMessage
    console.log(`Chat: ${msg.content}`);
  } else if (isErrorMessage(msg)) {
    // TypeScript knows this is an ErrorMessage
    console.log(`Error: ${msg.error} (${msg.severity})`);
  }
};
*/

export type { 
  WebSocketMessage, 
  ChatMessage, 
  ErrorMessage, 
  ServiceStatus,
  MediaEvent,
  Citation
};