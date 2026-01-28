// App.chat-only.tsx - Simple React chat interface
// Created: 2024-09-30
// Purpose: Clean chat UI based on test-simple-chat.html layout
// Connects to api_server_bridge.py for chat functionality

import React, { useState, useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import ServiceStatusPanel from './components/ServiceStatusPanel';
import ErrorPanel from './components/ErrorPanel';
import MessageBubble from './components/MessageBubble';
import SidebarsPanel, { SidebarContext, TreeData } from './components/SidebarsPanel';
import SidebarControlBar from './components/SidebarControlBar';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useToast } from './contexts/ToastContext';
import { reportCaughtError } from './utils/errorReporter';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  confidence_score?: number;  // 0.0-1.0, higher = more confident
  retrieved_context?: string[];  // Debug: What memory searches returned
}

interface ServiceHealth {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'starting' | 'stopped';
  latency?: number;
  last_check: string;
  error_count?: number;
}

interface ErrorEvent {
  id: string;
  timestamp: string;
  error: string;
  operation_context?: string;
  service?: string;
  severity: 'critical' | 'warning' | 'normal' | 'debug';
  attempted_fixes: string[];
  fix_success?: boolean;
  acknowledged?: boolean;
}

interface MemoryStats {
  episodic_count: number;
  working_memory_count: number;
  conversation_id: string;
  archival_failures?: number;
  archival_healthy?: boolean;
}

// API URL from environment, with localhost fallback for development
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const toast = useToast();

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [services, setServices] = useState<Record<string, ServiceHealth>>({});
  const [errors, setErrors] = useState<ErrorEvent[]>([]);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);
  const [sidebarTab, setSidebarTab] = useState<'status' | 'errors' | 'terminal' | 'sidebars'>('status');
  const [latency, setLatency] = useState<number | null>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Sidebar resize state
  const [sidebarWidth, setSidebarWidth] = useState(384); // default w-96
  const isResizing = useRef(false);
  // Sidebar collapse/notification state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [unreadSeverity, setUnreadSeverity] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ message: string; severity: string } | null>(null);
  const [stripHovered, setStripHovered] = useState(false);
  const prevErrorCount = useRef(0);

  // Sidebar/context management state
  const [contexts, setContexts] = useState<SidebarContext[]>([]);
  const [contextTree, setContextTree] = useState<TreeData | null>(null);
  const [activeContextId, setActiveContextId] = useState<string | null>(null);
  const [activeContextInfo, setActiveContextInfo] = useState<SidebarContext | null>(null);
  // Startup/initialization state
  const [needsInitialization, setNeedsInitialization] = useState<boolean | null>(null); // null = checking
  const [isCreatingRoot, setIsCreatingRoot] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermInstanceRef = useRef<Terminal | null>(null);
  const wasDisconnected = useRef(false); // Track previous connection state for auto-resume
  const disconnectTime = useRef<number | null>(null); // When disconnect started
  const pollFailures = useRef(0); // Count failures during outage for recovery report

  // Check startup state on mount - determines if we show init dialog or main chat
  useEffect(() => {
    checkStartupState();
    checkConnection();
    loadServiceStatus();
    loadErrors();

    // Poll for connection, service status, and errors (these always run)
    const interval = setInterval(() => {
      checkConnection();
      loadServiceStatus();
      loadErrors();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Load conversation data only after initialization is complete
  useEffect(() => {
    if (needsInitialization === false) {
      loadHistory(); // Load global chat history on startup
      loadMemoryStats();
      loadSidebars();
      loadSidebarTree();
      loadActiveContext();

      // Poll for these only when initialized
      const interval = setInterval(() => {
        loadMemoryStats();
        loadSidebars();
        loadActiveContext();
        // Tree doesn't need frequent polling - only changes on spawn/merge
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [needsInitialization]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize terminal when Terminal tab is shown
  useEffect(() => {
    if (sidebarTab === 'terminal' && terminalRef.current && !xtermInstanceRef.current) {
      const term = new Terminal({
        cursorBlink: true,
        theme: {
          background: '#000000',
          foreground: '#ffffff',
          cursor: '#ffffff'
        },
        fontSize: 14,
        fontFamily: 'monospace'
      });

      const fitAddon = new FitAddon();
      term.loadAddon(fitAddon);
      term.open(terminalRef.current);
      fitAddon.fit();

      term.writeln('Welcome to Memory Intelligence Terminal');
      term.writeln('Note: This is a placeholder terminal.');
      term.writeln('Full terminal integration with tmux coming soon...');
      term.writeln('');

      xtermInstanceRef.current = term;

      // Cleanup on unmount
      return () => {
        term.dispose();
        xtermInstanceRef.current = null;
      };
    }
  }, [sidebarTab]);

  // Sidebar resize drag handlers
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const newWidth = window.innerWidth - e.clientX;
      setSidebarWidth(Math.max(280, Math.min(800, newWidth)));
    };
    const handleMouseUp = () => {
      isResizing.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const startResize = () => {
    if (sidebarCollapsed) return; // Don't resize when collapsed
    isResizing.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const collapseSidebar = () => {
    setSidebarCollapsed(true);
  };

  const expandSidebar = () => {
    setSidebarCollapsed(false);
    setUnreadSeverity(null);
    setNotification(null);
  };

  // Watch for new errors while collapsed - trigger overlay notification
  useEffect(() => {
    if (sidebarCollapsed && errors.length > prevErrorCount.current) {
      const newErrors = errors.slice(prevErrorCount.current);
      const highestSeverity = newErrors.reduce((highest, err) => {
        const severityOrder: Record<string, number> = { critical: 4, warning: 3, normal: 2, debug: 1 };
        return (severityOrder[err.severity] || 0) > (severityOrder[highest] || 0) ? err.severity : highest;
      }, 'debug' as string);

      setUnreadSeverity(highestSeverity);
      setNotification({
        message: newErrors.length === 1
          ? newErrors[0].error
          : `${newErrors.length} new errors`,
        severity: highestSeverity
      });

      // Auto-dismiss after 3 seconds
      setTimeout(() => {
        setNotification(null);
      }, 3000);
    }
    prevErrorCount.current = errors.length;
  }, [errors, sidebarCollapsed]);

  const checkConnection = async () => {
    const start = performance.now();
    try {
      const response = await fetch(`${API_BASE}/health`);
      const elapsed = Math.round(performance.now() - start);
      const nowConnected = response.ok;

      // Auto-resume: if we were disconnected and now connected, report recovery
      if (nowConnected && wasDisconnected.current) {
        // Calculate outage duration and report recovery
        const outageDuration = disconnectTime.current
          ? Math.round((Date.now() - disconnectTime.current) / 1000)
          : 0;
        const failures = pollFailures.current;

        console.log(`[App] Connection RESTORED after ${outageDuration}s outage, ${failures} poll failures`);
        console.log('[App] Reporting recovery to ErrorHandler...');

        // Report recovery to ErrorHandler (closes the incident conceptually)
        reportCaughtError(
          new Error(`Reconnected after ${outageDuration}s and ${failures} polling failures`),
          'App',
          'checkConnection:recovery',
          {
            context: `outage_duration: ${outageDuration}s, poll_failures: ${failures}`,
            severity: 'low'  // Recovery is good news, low severity
          }
        ).then(result => {
          console.log('[App] Recovery report result:', result);
        });

        // Reset tracking
        wasDisconnected.current = false;
        disconnectTime.current = null;
        pollFailures.current = 0;

        // Re-check startup state to restore session instead of showing "Start Fresh"
        console.log('[App] Re-checking startup state for auto-resume...');
        checkStartupState();
      }

      setIsConnected(nowConnected);
      setLatency(nowConnected ? elapsed : null);

      // Track disconnection for auto-resume
      if (!nowConnected) {
        if (!wasDisconnected.current) {
          // First disconnect - record time and report
          console.log('[App] FIRST DISCONNECT detected (health check returned not-ok)');
          disconnectTime.current = Date.now();
          reportCaughtError(
            new Error('API health check failed'),
            'App',
            'checkConnection:disconnect',
            { severity: 'medium' }  // First disconnect is notable
          );
        }
        wasDisconnected.current = true;
        pollFailures.current++;
        console.log(`[App] Poll failure count: ${pollFailures.current}`);
      }
    } catch (error) {
      setIsConnected(false);
      setLatency(null);
      if (!wasDisconnected.current) {
        // First disconnect - record time and report
        console.log('[App] FIRST DISCONNECT detected (health check threw error)');
        disconnectTime.current = Date.now();
        reportCaughtError(error, 'App', 'checkConnection:disconnect', {
          severity: 'medium'
        });
      }
      wasDisconnected.current = true;
      pollFailures.current++;
      console.log(`[App] Poll failure count: ${pollFailures.current}`);
    }
  };

  const loadHistory = async () => {
    try {
      const response = await fetch(`${API_BASE}/history`);
      if (response.ok) {
        const data = await response.json();
        if (data.history && Array.isArray(data.history)) {
          const formattedMessages: Message[] = data.history.flatMap((exchange: any, index: number) => [
            {
              id: `user-${index}`,
              role: 'user' as const,
              content: exchange.user,
              timestamp: new Date().toISOString(),
            },
            {
              id: `assistant-${index}`,
              role: 'assistant' as const,
              content: exchange.assistant,
              timestamp: new Date().toISOString(),
            }
          ]);
          setMessages(formattedMessages);
        }
      }
    } catch (error) {
      console.error('Failed to load history:', error);
      reportCaughtError(error, 'App', 'loadHistory', { severity: 'trace' });
    }
  };

  const loadServiceStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/services/dashboard`);
      if (response.ok) {
        const data = await response.json();
        const serviceStatus: Record<string, ServiceHealth> = {};

        // Dashboard returns service names as root keys (skip _summary)
        Object.entries(data).forEach(([name, info]: [string, any]) => {
          if (name !== '_summary') {
            serviceStatus[name] = {
              status: info.status || 'unhealthy',
              latency: info.latency,
              last_check: info.last_check || new Date().toISOString(),
              error_count: info.error_count
            };
          }
        });

        setServices(serviceStatus);
      }
    } catch (error) {
      console.error('Failed to load service status:', error);
      reportCaughtError(error, 'App', 'loadServiceStatus', { severity: 'trace' });
    }
  };

  const loadErrors = async () => {
    try {
      const response = await fetch(`${API_BASE}/errors`);
      if (response.ok) {
        const data = await response.json();
        // Combine session and recent errors, remove duplicates
        const allErrors = [...(data.session || []), ...(data.recent || [])];
        const uniqueErrors = Array.from(
          new Map(allErrors.map(e => [e.id, e])).values()
        ).map((e: any) => ({
          ...e,
          // Provide defaults for ErrorPanel fields if backend doesn't send them
          attempted_fixes: e.attempted_fixes || [],
          fix_success: e.fix_success ?? null,
          acknowledged: e.acknowledged ?? false
        })) as ErrorEvent[];
        setErrors(uniqueErrors);
      }
    } catch (error) {
      console.error('Failed to load errors:', error);
      reportCaughtError(error, 'App', 'loadErrors', { severity: 'trace' });
    }
  };

  const loadMemoryStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/memory/stats`);
      if (response.ok) {
        const data = await response.json();
        setMemoryStats(data);
      }
    } catch (error) {
      console.error('Failed to load memory stats:', error);
      reportCaughtError(error, 'App', 'loadMemoryStats', { severity: 'trace' });
    }
  };

  // Sidebar/context management functions
  const loadSidebars = async () => {
    try {
      // Load all contexts including archived for tree metadata lookup
      const response = await fetch(`${API_BASE}/sidebars?limit=5000&include_archived=true`);
      if (response.ok) {
        const data = await response.json();
        setContexts(data.contexts || []);
      }
    } catch (error) {
      console.error('Failed to load sidebars:', error);
      reportCaughtError(error, 'App', 'loadSidebars', { severity: 'trace' });
    }
  };

  const loadSidebarTree = async () => {
    try {
      const response = await fetch(`${API_BASE}/sidebars/tree`);
      if (response.ok) {
        const data = await response.json();
        setContextTree(data.tree || null);
      }
    } catch (error) {
      console.error('Failed to load sidebar tree:', error);
      reportCaughtError(error, 'App', 'loadSidebarTree', { severity: 'trace' });
    }
  };

  const loadActiveContext = async () => {
    try {
      const response = await fetch(`${API_BASE}/sidebars/active`);
      if (response.ok) {
        const data = await response.json();
        setActiveContextId(data.active?.id || null);
        if (data.active) {
          setActiveContextInfo({
            id: data.active.id,
            parent_id: data.active.parent_id || null,
            status: data.active.status || 'active',
            reason: data.active.reason || data.active.task_description || null,
            display_name: data.active.display_name || null,
            created_at: data.active.created_at || null,
            exchange_count: data.active.exchange_count || 0,
            inherited_count: data.active.inherited_count,
          });
        } else {
          setActiveContextInfo(null);
        }
      }
    } catch (error) {
      console.error('Failed to load active context:', error);
      reportCaughtError(error, 'App', 'loadActiveContext', { severity: 'trace' });
    }
  };

  // Startup state check - determines if we need to show initialization dialog
  const checkStartupState = async () => {
    try {
      const response = await fetch(`${API_BASE}/sidebars/startup-state`);
      if (response.ok) {
        const data = await response.json();
        setNeedsInitialization(data.needs_initialization);
        if (!data.needs_initialization) {
          setActiveContextId(data.active_context_id);
          // Also reload data when resuming from disconnect
          loadHistory();
          loadSidebars();
          loadSidebarTree();
          loadActiveContext();
        }
      } else {
        // API error - preserve existing state, don't force init dialog
        // If we were initialized (false), stay initialized
        // If we were checking (null), keep checking - polling will retry
        setNeedsInitialization((prev) => prev === false ? false : prev);
      }
    } catch (error) {
      console.error('Failed to check startup state:', error);
      // Network error - don't show init dialog, stay in checking/waiting state
      // The connection polling will retry checkStartupState when API returns
      // Only preserve false (already initialized), otherwise stay null (checking)
      setNeedsInitialization((prev) => prev === false ? false : null);
      reportCaughtError(error, 'App', 'checkStartupState', { severity: 'trace' });
    }
  };

  // Create initial root context - called from initialization dialog
  const createRootContext = async (taskDescription: string = 'Main conversation') => {
    setIsCreatingRoot(true);
    try {
      const response = await fetch(`${API_BASE}/sidebars/create-root`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_description: taskDescription,
          created_by: 'human'
        })
      });
      if (response.ok) {
        const data = await response.json();
        setActiveContextId(data.id);
        setNeedsInitialization(false);
        // Refresh sidebar data
        await Promise.all([loadSidebars(), loadSidebarTree(), loadActiveContext()]);
      } else {
        console.error('Failed to create root context');
      }
    } catch (error) {
      console.error('Failed to create root context:', error);
      reportCaughtError(error, 'App', 'createRootContext', {
        severity: 'critical'  // Can't start conversations without root
      });
    } finally {
      setIsCreatingRoot(false);
    }
  };

  const spawnSidebar = async (parentId: string, reason: string) => {
    try {
      const response = await fetch(`${API_BASE}/sidebars/spawn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ parent_id: parentId, reason })
      });
      if (response.ok) {
        const data = await response.json();
        // Refresh sidebar list and tree after spawning
        await Promise.all([loadSidebars(), loadSidebarTree(), loadActiveContext()]);
        return data;
      }
    } catch (error) {
      console.error('Failed to spawn sidebar:', error);
      reportCaughtError(error, 'App', 'spawnSidebar', {
        context: `parentId: ${parentId}, reason: ${reason}`,
        severity: 'high'
      });
    }
  };

  const focusSidebar = async (contextId: string) => {
    try {
      // Focus the sidebar on the backend
      const response = await fetch(`${API_BASE}/sidebars/${contextId}/focus`, {
        method: 'POST'
      });
      if (response.ok) {
        setActiveContextId(contextId);

        // Load the context's messages
        const contextResponse = await fetch(`${API_BASE}/sidebars/${contextId}`);
        if (contextResponse.ok) {
          const data = await contextResponse.json();
          const localMemory = data.context?.local_memory || [];

          // Format local_memory into Message[] format
          // Handles both formats: {role, content} and {user, assistant, retrieved_memories}
          const formattedMessages: Message[] = localMemory.flatMap((exchange: any, index: number) => {
            const msgs: Message[] = [];

            // Handle {role: 'user'/'assistant', content: '...'} format
            if (exchange.role === 'user') {
              msgs.push({
                id: `user-${contextId}-${index}`,
                role: 'user' as const,
                content: exchange.content,
                timestamp: exchange.timestamp || new Date().toISOString(),
              });
            } else if (exchange.role === 'assistant') {
              msgs.push({
                id: `assistant-${contextId}-${index}`,
                role: 'assistant' as const,
                content: exchange.content,
                timestamp: exchange.timestamp || new Date().toISOString(),
                retrieved_context: exchange.retrieved_memories,  // Include if present
              });
            }
            // Handle {user: '...', assistant: '...', retrieved_memories: [...]} format
            else if (exchange.user && exchange.assistant) {
              msgs.push({
                id: `user-${contextId}-${index}`,
                role: 'user' as const,
                content: exchange.user,
                timestamp: exchange.timestamp || new Date().toISOString(),
              });
              msgs.push({
                id: `assistant-${contextId}-${index}`,
                role: 'assistant' as const,
                content: exchange.assistant,
                timestamp: exchange.timestamp || new Date().toISOString(),
                retrieved_context: exchange.retrieved_memories,  // Persisted memories that influenced response
              });
            }
            return msgs;
          });

          setMessages(formattedMessages);
        }
      }
    } catch (error) {
      console.error('Failed to focus sidebar:', error);
      reportCaughtError(error, 'App', 'focusSidebar', {
        context: `contextId: ${contextId}`,
        severity: 'high'  // Switching context is core functionality
      });
    }
  };

  const pauseSidebar = async (contextId: string) => {
    try {
      await fetch(`${API_BASE}/sidebars/${contextId}/pause`, { method: 'POST' });
      await Promise.all([loadSidebars(), loadSidebarTree()]);
    } catch (error) {
      console.error('Failed to pause sidebar:', error);
    }
  };

  const resumeSidebar = async (contextId: string) => {
    try {
      await fetch(`${API_BASE}/sidebars/${contextId}/resume`, { method: 'POST' });
      await Promise.all([loadSidebars(), loadSidebarTree()]);
    } catch (error) {
      console.error('Failed to resume sidebar:', error);
    }
  };

  const mergeSidebar = async (contextId: string) => {
    try {
      await fetch(`${API_BASE}/sidebars/${contextId}/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_summarize: true })  // Let backend summarize
      });
      await Promise.all([loadSidebars(), loadSidebarTree()]);
    } catch (error) {
      console.error('Failed to merge sidebar:', error);
    }
  };

  const archiveSidebar = async (contextId: string) => {
    try {
      await fetch(`${API_BASE}/sidebars/${contextId}/archive`, { method: 'POST' });
      await Promise.all([loadSidebars(), loadSidebarTree()]);
    } catch (error) {
      console.error('Failed to archive sidebar:', error);
    }
  };

  // Error panel handlers
  const acknowledgeError = async (errorId: string) => {
    try {
      await fetch(`${API_BASE}/errors/${errorId}/acknowledge`, { method: 'POST' });
      setErrors(prev => prev.map(e =>
        e.id === errorId ? { ...e, acknowledged: true } : e
      ));
      toast.info('Error acknowledged');
    } catch (error) {
      console.error('Failed to acknowledge error:', error);
      toast.error('Failed to acknowledge error');
      reportCaughtError(error, 'App', 'acknowledgeError', {
        context: `errorId: ${errorId}`,
        severity: 'low'  // Error panel action, not critical
      });
    }
  };

  const clearErrors = async () => {
    try {
      await fetch(`${API_BASE}/errors/clear`, { method: 'POST' });
      setErrors([]);
      toast.success('All errors cleared');
    } catch (error) {
      console.error('Failed to clear errors:', error);
      toast.error('Failed to clear errors');
      reportCaughtError(error, 'App', 'clearErrors', {
        severity: 'low'  // Error panel action, not critical
      });
    }
  };

  const reportFix = async (errorId: string, worked: boolean) => {
    try {
      const response = await fetch(`${API_BASE}/errors/${errorId}/report-fix`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ worked })
      });
      if (!response.ok) {
        // Endpoint may not exist yet - still update UI but warn
        console.warn(`Fix report endpoint returned ${response.status} - backend may need this endpoint implemented`);
      }
      // Update UI regardless (optimistic update)
      setErrors(prev => prev.map(e =>
        e.id === errorId ? { ...e, fix_success: worked } : e
      ));
      toast.success(worked ? 'Fix confirmed as working' : 'Fix marked as not working');
    } catch (error) {
      console.error('Failed to report fix:', error);
      toast.error('Failed to report fix status');
      // Show error in UI by adding a system message
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Failed to report fix to backend: ${error}. (Endpoint /errors/{id}/report-fix may need implementation)`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  // Service action handler for ServiceStatusPanel
  const handleServiceAction = async (serviceName: string, action: 'start' | 'stop' | 'restart') => {
    try {
      // Call the correct endpoint based on action
      const response = await fetch(`${API_BASE}/services/${serviceName}/${action}`, {
        method: 'POST'
      });
      const data = await response.json();

      if (data.status === 'success') {
        const pastTense = action === 'stop' ? 'stopped' : `${action}ed`;
        toast.success(`${serviceName} ${pastTense} successfully`);
        // Refresh service status after action
        loadServiceStatus();
      } else {
        toast.error(`Failed to ${action} ${serviceName}: ${data.message || 'Unknown error'}`);
        console.warn(`Service ${action} returned:`, data.message);
      }
    } catch (error) {
      toast.error(`Failed to ${action} ${serviceName}`);
      console.error(`Failed to ${action} service ${serviceName}:`, error);
      reportCaughtError(error, 'App', 'handleServiceAction', {
        context: `service: ${serviceName}, action: ${action}`,
        severity: 'medium'
      });
    }
  };

  // Scroll handling for chat
  const handleScroll = () => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    setShowScrollButton(distanceFromBottom > 100);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading || !isConnected) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString()
    };

    // Add user message immediately
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    // Reset textarea height after clearing
    if (inputRef.current) {
      inputRef.current.style.height = '38px';
    }
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage.content })
      });

      if (response.ok) {
        const data = await response.json();
        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: data.response,
          timestamp: new Date().toISOString(),
          confidence_score: data.confidence_score,  // Capture confidence from backend
          retrieved_context: data.retrieved_context  // Debug: Captured memories
        };
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Failed to send message: ${error}`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
      reportCaughtError(error, 'App', 'sendMessage', {
        context: `activeContext: ${activeContextId || 'root'}`,
        severity: 'high'  // Core functionality failure
      });
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Build breadcrumb path from active context to root
  const buildBreadcrumbPath = () => {
    if (!activeContextId) {
      return [{ id: 'root', label: 'Main', isRoot: true }];
    }

    const path: { id: string; label: string; isRoot: boolean }[] = [];
    let currentId: string | null = activeContextId;

    // Walk up the parent chain
    while (currentId) {
      let ctx = contexts.find(c => c.id === currentId);
      // Fallback to active context info if not in paginated list (e.g. archived)
      if (!ctx && currentId === activeContextId && activeContextInfo) {
        ctx = activeContextInfo;
      }
      if (ctx) {
        path.unshift({
          id: ctx.id,
          label: ctx.display_name || ctx.reason || ctx.id,
          isRoot: ctx.parent_id === null
        });
        currentId = ctx.parent_id;
      } else {
        // Context not in list - show ID as fallback
        path.unshift({
          id: currentId,
          label: currentId,
          isRoot: path.length === 0
        });
        break;
      }
    }

    // If path is empty, show default
    if (path.length === 0) {
      return [{ id: 'root', label: 'Main', isRoot: true }];
    }

    return path;
  };

  // Get active context info for SidebarControlBar
  const getActiveContextInfo = () => {
    if (!activeContextId) return null;
    const ctx = contexts.find(c => c.id === activeContextId) || activeContextInfo;
    if (!ctx) return null;
    return {
      id: ctx.id,
      reason: ctx.reason,
      parent_id: ctx.parent_id,
      status: ctx.status,
      exchange_count: ctx.exchange_count,
      inherited_count: ctx.inherited_count
    };
  };

  // Handle "back to parent" from control bar
  const handleBackToParent = () => {
    const activeCtx = contexts.find(c => c.id === activeContextId);
    if (activeCtx?.parent_id) {
      focusSidebar(activeCtx.parent_id);
    }
  };

  // Handle fork from control bar (spawns from current active context)
  const handleFork = (reason: string) => {
    const parentId = activeContextId || contexts.find(c => c.parent_id === null)?.id;
    if (parentId) {
      spawnSidebar(parentId, reason);
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-[#1e1e1e] overflow-hidden">
      {/* Header */}
      <header className="h-[73px] bg-[#252526] border-b border-[#3e3e42] p-4 flex items-center justify-between flex-shrink-0">
        <h1 className="text-xl font-bold text-[#cccccc]">
          Memory Intelligence Chat
        </h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          {latency !== null && (
            <span className={`text-sm font-mono ${
              latency < 100 ? 'text-green-400' :
              latency < 300 ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {latency}ms
            </span>
          )}
        </div>
      </header>

      {/* Initialization Dialog - shown when no contexts exist */}
      {needsInitialization === null ? (
        // Checking startup state / waiting for API
        <main className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-400">
            <div className="animate-pulse text-2xl mb-2">...</div>
            <p>{isConnected ? 'Loading session...' : 'Waiting for API connection...'}</p>
            {!isConnected && (
              <p className="text-sm text-gray-500 mt-2">Will auto-resume when connected</p>
            )}
          </div>
        </main>
      ) : needsInitialization === true ? (
        // No contexts - show Start Fresh dialog
        <main className="flex-1 flex items-center justify-center">
          <div className="bg-[#252526] border border-[#3e3e42] rounded-lg p-8 max-w-md text-center">
            <h2 className="text-2xl font-bold text-[#cccccc] mb-4">
              Welcome to Memory Intelligence
            </h2>
            <p className="text-gray-400 mb-6">
              No conversation history found. Start a new conversation to begin.
            </p>
            <div className="space-y-4">
              <button
                onClick={() => createRootContext('Main conversation')}
                disabled={isCreatingRoot}
                className={`w-full px-6 py-3 rounded-lg text-lg font-medium ${
                  isCreatingRoot
                    ? 'bg-gray-600 text-gray-400 cursor-wait'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {isCreatingRoot ? 'Starting...' : 'Start Fresh'}
              </button>
              <p className="text-sm text-gray-500">
                This will create a new conversation context.
              </p>
            </div>
          </div>
        </main>
      ) : (
      /* Main content - shown when initialized */
      <main className="flex-1 flex overflow-hidden min-h-0">
        {/* Chat area */}
        <div className="flex-1 flex flex-col p-4 min-w-0">
          {/* Chat container */}
          <div className="h-full bg-[#252526] border border-[#3e3e42] rounded-lg flex flex-col relative min-w-0 overflow-hidden">
            {/* Messages area */}
            <div
              ref={messagesContainerRef}
              onScroll={handleScroll}
              className="flex-1 overflow-y-auto p-4 border-b border-[#3e3e42]"
            >
              {messages.length === 0 ? (
                <div className="text-center text-gray-500 py-8">
                  <p>Start a conversation!</p>
                  <p className="text-sm mt-2">
                    Type a message below to begin.
                  </p>
                </div>
              ) : (
                messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Scroll to bottom button - positioned relative to chat container */}
            {showScrollButton && (
              <button
                onClick={scrollToBottom}
                className="absolute bottom-32 right-8 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center shadow-lg hover:bg-blue-700 transition-colors z-10"
                title="Scroll to bottom"
              >
                ↓
              </button>
            )}

            {/* Sidebar control bar - shows current context, fork button, breadcrumbs */}
            <SidebarControlBar
              activeContext={getActiveContextInfo()}
              breadcrumbPath={buildBreadcrumbPath()}
              onFork={handleFork}
              onNavigate={focusSidebar}
              onBackToParent={handleBackToParent}
            />

            {/* Input area */}
            <div className="p-4 flex gap-2 items-end flex-shrink-0">
              <textarea
                ref={inputRef}
                value={inputMessage}
                onChange={(e) => {
                  setInputMessage(e.target.value);
                  // Auto-expand height
                  e.target.style.height = 'auto';
                  e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
                }}
                onKeyDown={handleKeyPress}
                placeholder={isLoading ? "Processing..." : "Type a message..."}
                disabled={isLoading || !isConnected}
                rows={1}
                className="flex-1 p-2 border border-[#3e3e42] rounded text-sm text-[#cccccc] bg-[#1e1e1e] focus:outline-none focus:border-blue-500 resize-none overflow-y-auto break-words"
                style={{
                  minHeight: '38px',
                  maxHeight: '200px',
                  whiteSpace: 'pre-wrap',
                  overflowWrap: 'break-word',
                  wordWrap: 'break-word'
                }}
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !isConnected || !inputMessage.trim()}
                className={`px-4 py-2 rounded border-none ${
                  isLoading || !isConnected || !inputMessage.trim()
                    ? 'bg-[#3e3e42] text-gray-500 cursor-not-allowed'
                    : 'bg-blue-600 text-white cursor-pointer hover:bg-blue-700'
                }`}
              >
                {isLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        </div>

        {sidebarCollapsed ? (
          <>
            {/* Collapsed toggle strip */}
            <div
              className="relative flex-shrink-0"
              onMouseEnter={() => setStripHovered(true)}
              onMouseLeave={() => setStripHovered(false)}
            >
              <div
                onClick={expandSidebar}
                className={`h-full flex items-center justify-center cursor-pointer transition-all duration-200 ${
                  unreadSeverity
                    ? `w-3 ${
                        unreadSeverity === 'critical' ? 'bg-red-600' :
                        unreadSeverity === 'warning' ? 'bg-yellow-600' :
                        unreadSeverity === 'normal' ? 'bg-orange-600' :
                        'bg-blue-600'
                      }`
                    : stripHovered
                      ? 'w-3 bg-[#3e3e42]'
                      : 'w-0.5 bg-[#3e3e42]'
                }`}
                title="Expand sidebar"
              >
                {(stripHovered || unreadSeverity) && (
                  <ChevronLeft className="h-4 w-4 text-gray-200" />
                )}
              </div>
            </div>

            {/* Error notification overlay */}
            <div
              className={`fixed top-20 right-4 z-50 transition-all duration-300 ${
                notification
                  ? 'opacity-100 translate-x-0'
                  : 'opacity-0 translate-x-full pointer-events-none'
              }`}
            >
              {notification && (
                <div
                  className={`px-4 py-3 rounded-lg border backdrop-blur-sm bg-opacity-90 shadow-lg max-w-sm cursor-pointer ${
                    notification.severity === 'critical' ? 'bg-red-900/90 border-red-600 text-red-200' :
                    notification.severity === 'warning' ? 'bg-yellow-900/90 border-yellow-600 text-yellow-200' :
                    notification.severity === 'normal' ? 'bg-orange-900/90 border-orange-600 text-orange-200' :
                    'bg-blue-900/90 border-blue-600 text-blue-200'
                  }`}
                  onClick={expandSidebar}
                >
                  <div className="text-sm font-medium">{notification.message}</div>
                  <div className="text-xs opacity-75 mt-1">Click to view</div>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            {/* Resize Handle with collapse button */}
            <div className="relative flex-shrink-0 group">
              <div
                onMouseDown={startResize}
                className="w-1.5 h-full bg-[#3e3e42] hover:bg-blue-500 cursor-col-resize transition-colors"
                title="Drag to resize"
              />
              <button
                onClick={collapseSidebar}
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-gray-700 border border-gray-500 text-gray-400 hover:text-gray-200 hover:bg-gray-600 items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hidden group-hover:flex z-10"
                title="Collapse sidebar"
              >
                <ChevronRight className="h-3 w-3" />
              </button>
            </div>

            {/* Monitoring Sidebar with Tabs */}
            <div className="bg-[#252526] flex-shrink-0 flex flex-col overflow-hidden" style={{ width: `${sidebarWidth}px` }}>
              {/* Tabs */}
              <div className="flex border-b border-[#3e3e42] flex-shrink-0">
                {(['status', 'errors', 'sidebars', 'terminal'] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setSidebarTab(tab)}
                    className={`flex-1 p-3 border-none cursor-pointer text-sm ${
                      sidebarTab === tab
                        ? 'bg-[#252526] font-semibold text-[#cccccc] border-b-2 border-b-blue-600'
                        : 'bg-[#1e1e1e] font-normal text-gray-500 hover:text-gray-400'
                    }`}
                  >
                    {tab === 'status' && 'Status'}
                    {tab === 'errors' && `Errors${errors.length > 0 ? ` (${errors.length})` : ''}`}
                    {tab === 'sidebars' && 'Sidebars'}
                    {tab === 'terminal' && 'Terminal'}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div className="flex-1 overflow-y-auto p-4">
                {sidebarTab === 'status' ? (
                  <ServiceStatusPanel
                    services={services}
                    conversationId={memoryStats?.conversation_id}
                    onServiceAction={handleServiceAction}
                  />
                ) : sidebarTab === 'errors' ? (
                  <ErrorPanel
                    errors={errors}
                    onAcknowledge={acknowledgeError}
                    onClear={clearErrors}
                    onReportFix={reportFix}
                  />
                ) : sidebarTab === 'sidebars' ? (
                  <SidebarsPanel
                    contexts={contexts}
                    tree={contextTree}
                    activeContextId={activeContextId}
                    onSpawn={spawnSidebar}
                    onCreateRoot={createRootContext}
                    onFocus={focusSidebar}
                    onPause={pauseSidebar}
                    onResume={resumeSidebar}
                    onMerge={mergeSidebar}
                    onArchive={archiveSidebar}
                    onRefresh={() => {
                      loadSidebars();
                      loadSidebarTree();
                    }}
                  />
                ) : (
                  <>
                    <h3 className="mb-4 text-lg font-bold text-[#cccccc]">
                      Terminal
                    </h3>
                    <div
                      ref={terminalRef}
                      className="h-[calc(100%-40px)] bg-black rounded p-2"
                    />
                  </>
                )}
              </div>
            </div>
          </>
        )}
      </main>
      )}
    </div>
  );
}

export default App;
