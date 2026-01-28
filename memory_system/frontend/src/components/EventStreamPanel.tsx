// components/EventStreamPanel.tsx
// Visibility Stream - Operator sees what Claude sees
// Per VISIBILITY_STREAM_PRD.md: Poison detection + system visibility

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible';
import { ScrollArea } from './ui/scroll-area';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import {
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  RefreshCw,
  Pause,
  Play,
  Search,
  Filter,
  AlertTriangle,
  Brain,
  Activity,
  Bug,
  Zap
} from 'lucide-react';

// Event interface matching backend VisibilityEvent.to_dict()
interface VisibilityEvent {
  sequence: number;
  timestamp: string;
  type: string;
  payload: Record<string, unknown>;
  tier: number;  // 1=critical, 2=system, 3=debug
  tier_name: string;
  context_id: string;
  actor: string;
}

interface EventStreamPanelProps {
  wsUrl?: string;
  maxEvents?: number;
  defaultTiers?: string[];
}

// WebSocket URL from environment, with localhost fallback
const DEFAULT_WS_URL = import.meta.env.VITE_WS_EVENTS_URL || 'ws://localhost:8000/ws/events';

const EventStreamPanel: React.FC<EventStreamPanelProps> = ({
  wsUrl = DEFAULT_WS_URL,
  maxEvents = 500,
  defaultTiers = ['critical', 'system']
}) => {
  // State
  const [events, setEvents] = useState<VisibilityEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused] = useState(false);
  const [activeTiers, setActiveTiers] = useState<Set<string>>(new Set(defaultTiers));
  const [expandedEvents, setExpandedEvents] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [eventTypes, setEventTypes] = useState<Record<string, string>>({});

  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttemptRef = useRef<number>(0);

  // Refs for values that shouldn't trigger reconnection
  const activeTiersRef = useRef<Set<string>>(activeTiers);
  const pausedRef = useRef<boolean>(paused);

  // Keep refs in sync with state
  useEffect(() => { activeTiersRef.current = activeTiers; }, [activeTiers]);
  useEffect(() => { pausedRef.current = paused; }, [paused]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[EventStream] Connected to visibility stream');
      setConnected(true);
      reconnectAttemptRef.current = 0; // Reset backoff on successful connection

      // Request tier configuration using ref (doesn't trigger reconnection)
      ws.send(JSON.stringify({
        type: 'set_stream_tiers',
        tiers: Array.from(activeTiersRef.current)
      }));
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (e) {
        console.error('[EventStream] Malformed message received:', event.data);
        return; // Skip this message, don't crash the component
      }

      switch (data.type) {
        case 'event_stream_connected':
          setEventTypes(data.event_types || {});
          console.log('[EventStream] Stream ready, known types:', Object.keys(data.event_types || {}).length);
          break;

        case 'event_history':
          // Catch-up events from buffer (check ref, not state)
          if (!pausedRef.current && data.events) {
            setEvents(prev => {
              const newEvents = [...data.events, ...prev];
              return newEvents.slice(0, maxEvents);
            });
          }
          break;

        case 'tiers_updated':
          console.log('[EventStream] Tiers updated:', data.stream_tiers);
          break;

        case 'emitter_stats':
          setStats(data.stats);
          break;

        case 'pong':
          // Keep-alive response
          break;

        default:
          // This is a live event (check ref, not state)
          if (data.sequence !== undefined && !pausedRef.current) {
            setEvents(prev => {
              const newEvents = [data, ...prev];
              return newEvents.slice(0, maxEvents);
            });
          }
      }
    };

    ws.onclose = () => {
      console.log('[EventStream] Disconnected');
      setConnected(false);
      wsRef.current = null;

      // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
      const attempt = reconnectAttemptRef.current;
      const delay = Math.min(1000 * Math.pow(2, attempt), 30000);
      reconnectAttemptRef.current = attempt + 1;

      console.log(`[EventStream] Reconnecting in ${delay / 1000}s (attempt ${attempt + 1})`);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, delay);
    };

    ws.onerror = (error) => {
      console.error('[EventStream] WebSocket error:', error);
    };

    wsRef.current = ws;
  }, [wsUrl, maxEvents]); // Only reconnect when URL or maxEvents changes

  // Cleanup on unmount
  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  // Update tier configuration when activeTiers changes
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'set_stream_tiers',
        tiers: Array.from(activeTiers)
      }));
    }
  }, [activeTiers]);

  // Filter events
  const filteredEvents = React.useMemo(() => {
    return events.filter(event => {
      // Tier filter
      if (!activeTiers.has(event.tier_name)) return false;

      // Type filter
      if (typeFilter && event.type !== typeFilter) return false;

      // Search filter
      if (searchTerm) {
        const searchLower = searchTerm.toLowerCase();
        const matchesType = event.type.toLowerCase().includes(searchLower);
        const matchesPayload = JSON.stringify(event.payload).toLowerCase().includes(searchLower);
        const matchesContext = event.context_id.toLowerCase().includes(searchLower);
        if (!matchesType && !matchesPayload && !matchesContext) return false;
      }

      return true;
    });
  }, [events, activeTiers, typeFilter, searchTerm]);

  // Tier colors and icons
  const getTierStyle = (tierName: string) => {
    switch (tierName) {
      case 'critical':
        return {
          bg: 'bg-red-50 border-red-200',
          badge: 'bg-red-100 text-red-800',
          icon: <AlertTriangle className="h-4 w-4 text-red-500" />
        };
      case 'system':
        return {
          bg: 'bg-blue-50 border-blue-200',
          badge: 'bg-blue-100 text-blue-800',
          icon: <Activity className="h-4 w-4 text-blue-500" />
        };
      case 'debug':
        return {
          bg: 'bg-gray-50 border-gray-200',
          badge: 'bg-gray-100 text-gray-800',
          icon: <Bug className="h-4 w-4 text-gray-500" />
        };
      default:
        return {
          bg: 'bg-white border-gray-200',
          badge: 'bg-gray-100 text-gray-800',
          icon: <Zap className="h-4 w-4 text-gray-500" />
        };
    }
  };

  // Event type icon
  const getEventIcon = (eventType: string) => {
    if (eventType.includes('memory')) return <Brain className="h-4 w-4" />;
    if (eventType.includes('error')) return <AlertTriangle className="h-4 w-4" />;
    if (eventType.includes('context') || eventType.includes('sidebar')) return <Activity className="h-4 w-4" />;
    return <Zap className="h-4 w-4" />;
  };

  // Toggle tier
  const toggleTier = (tier: string) => {
    setActiveTiers(prev => {
      const next = new Set(prev);
      if (next.has(tier)) {
        next.delete(tier);
      } else {
        next.add(tier);
      }
      return next;
    });
  };

  // Toggle event expansion
  const toggleExpanded = (seq: number) => {
    setExpandedEvents(prev => {
      const next = new Set(prev);
      if (next.has(seq)) {
        next.delete(seq);
      } else {
        next.add(seq);
      }
      return next;
    });
  };

  // Format timestamp
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
  };

  // Request stats
  const requestStats = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'get_stats' }));
    }
  };

  // Get unique event types from current events
  const uniqueTypes = React.useMemo(() => {
    return Array.from(new Set(events.map(e => e.type))).sort();
  }, [events]);

  // Count by tier
  const tierCounts = React.useMemo(() => {
    const counts = { critical: 0, system: 0, debug: 0 };
    events.forEach(e => {
      if (e.tier_name in counts) {
        counts[e.tier_name as keyof typeof counts]++;
      }
    });
    return counts;
  }, [events]);

  return (
    <TooltipProvider>
    <Card className="w-full h-full flex flex-col">
      <CardHeader className="pb-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5" />
            Visibility Stream
            {connected ? (
              <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                Live
              </Badge>
            ) : (
              <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">
                Disconnected
              </Badge>
            )}
          </CardTitle>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPaused(!paused)}
              title={paused ? 'Resume stream' : 'Pause stream'}
            >
              {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={requestStats}
              title="Get stats"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEvents([])}
              title="Clear events"
            >
              Clear
            </Button>
          </div>
        </div>

        {/* Tier filters */}
        <div className="flex gap-2 items-center flex-wrap mt-2">
          <span className="text-sm text-gray-500">Tiers:</span>
          {['critical', 'system', 'debug'].map((tier) => (
            <Button
              key={tier}
              variant={activeTiers.has(tier) ? "default" : "outline"}
              size="sm"
              onClick={() => toggleTier(tier)}
              className="flex items-center gap-1"
            >
              {activeTiers.has(tier) ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
              {tier}
              <Badge variant="secondary" className="ml-1 text-xs">
                {tierCounts[tier as keyof typeof tierCounts]}
              </Badge>
            </Button>
          ))}
        </div>

        {/* Search and type filter */}
        <div className="flex gap-2 items-center mt-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search events..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 border rounded text-sm"
            />
          </div>

          <div className="relative">
            <Filter className="absolute left-2 top-2 h-4 w-4 text-gray-400" />
            <select
              value={typeFilter || ''}
              onChange={(e) => setTypeFilter(e.target.value || null)}
              className="pl-8 pr-3 py-1.5 border rounded text-sm appearance-none bg-white"
            >
              <option value="">All types</option>
              {uniqueTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-hidden p-0">
        <ScrollArea className="h-full p-4" ref={scrollRef}>
          {filteredEvents.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              {events.length === 0
                ? "Waiting for events..."
                : "No events match your filters"}
            </div>
          ) : (
            <div className="space-y-2">
              {filteredEvents.map((event) => {
                const style = getTierStyle(event.tier_name);
                const isExpanded = expandedEvents.has(event.sequence);

                return (
                  <Collapsible
                    key={event.sequence}
                    open={isExpanded}
                    onOpenChange={() => toggleExpanded(event.sequence)}
                    className={`border rounded-lg ${style.bg}`}
                  >
                    <CollapsibleTrigger className="flex items-center gap-2 p-2 w-full text-left cursor-pointer hover:bg-gray-50/50 rounded-lg">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-gray-400" />
                      )}

                      {style.icon}

                      <span className="font-mono text-xs text-gray-400">
                        #{event.sequence}
                      </span>

                      <span className="text-gray-400">
                        {getEventIcon(event.type)}
                      </span>

                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Badge variant="outline" className={`${style.badge} cursor-help`}>
                            {event.type}
                          </Badge>
                        </TooltipTrigger>
                        <TooltipContent>
                          <p>{eventTypes[event.type] || 'No description available'}</p>
                        </TooltipContent>
                      </Tooltip>

                      <span className="text-xs text-gray-500 flex-1">
                        {event.context_id}
                      </span>

                      <span className="text-xs text-gray-400">
                        {formatTime(event.timestamp)}
                      </span>
                    </CollapsibleTrigger>

                    <CollapsibleContent className="px-4 pb-3 border-t bg-white">
                      <div className="mt-2 space-y-2">
                        <div className="flex gap-4 text-xs text-gray-500">
                          <span><strong>Actor:</strong> {event.actor}</span>
                          <span><strong>Tier:</strong> {event.tier_name}</span>
                          <span><strong>Context:</strong> {event.context_id}</span>
                        </div>

                        <div className="text-xs">
                          <strong>Payload:</strong>
                          <pre className="mt-1 p-2 bg-gray-50 rounded overflow-x-auto text-xs">
                            {JSON.stringify(event.payload, null, 2)}
                          </pre>
                        </div>

                        <div className="text-xs text-gray-400">
                          {event.timestamp}
                        </div>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </CardContent>

      {/* Footer stats */}
      <div className="flex-shrink-0 px-4 py-2 border-t bg-gray-50 text-xs text-gray-500">
        <div className="flex justify-between">
          <span>
            Showing {filteredEvents.length} of {events.length} events
          </span>
          <span>
            {connected ? 'Connected' : 'Disconnected'}
            {paused && ' (Paused)'}
          </span>
        </div>
        {stats && (
          <div className="mt-1 pt-1 border-t border-gray-200 flex gap-4 text-gray-400">
            {Object.entries(stats).map(([key, value]) => (
              <span key={key}>
                <strong>{key}:</strong> {String(value)}
              </span>
            ))}
          </div>
        )}
      </div>
    </Card>
    </TooltipProvider>
  );
};

export default EventStreamPanel;
