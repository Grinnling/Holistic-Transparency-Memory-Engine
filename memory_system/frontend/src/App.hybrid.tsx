// App.hybrid.tsx - Hybrid UI: Chat + xterm terminal + Error + Status monitoring
// Created: 2024-09-30
// Purpose: Complete monitoring interface combining all components
// - Chat: Main conversation interface via api_server_bridge.py
// - xterm: Terminal output for tooling commands
// - Error Panel: Real-time error tracking
// - Status Panel: Service health monitoring

import React, { useState, useEffect, useRef } from 'react';
import { TerminalDisplay } from './components/TerminalDisplay';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

interface ErrorEvent {
  id: string;
  timestamp: string;
  error: string;
  severity: 'critical' | 'warning' | 'normal' | 'debug';
  operation_context?: string;
  service?: string;
}

interface ServiceHealth {
  status: 'healthy' | 'unhealthy' | 'degraded';
  latency?: number;
  last_check?: string;
}

const API_BASE = 'http://localhost:8000';

function App() {
  // Layout state
  const [layout, setLayout] = useState<'chat-only' | 'split' | 'terminal-only'>('split');
  const [rightPanel, setRightPanel] = useState<'status' | 'errors'>('status');

  // Chat state
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Monitoring state
  const [errors, setErrors] = useState<ErrorEvent[]>([]);
  const [services, setServices] = useState<Record<string, ServiceHealth>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load initial data
  useEffect(() => {
    loadHistory();
    loadErrors();
    loadServiceStatus();

    // Poll for updates every 5 seconds
    const interval = setInterval(() => {
      loadErrors();
      loadServiceStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadHistory = async () => {
    try {
      const response = await fetch(`${API_BASE}/history`);
      setIsConnected(response.ok);

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
      setIsConnected(false);
    }
  };

  const loadErrors = async () => {
    try {
      const response = await fetch(`${API_BASE}/errors`);
      if (response.ok) {
        const data = await response.json();
        // Combine session and recent errors
        const allErrors = [...(data.session || []), ...(data.recent || [])];
        // Deduplicate by ID
        const uniqueErrors = Array.from(
          new Map(allErrors.map(e => [e.id, e])).values()
        );
        setErrors(uniqueErrors);
      }
    } catch (error) {
      console.error('Failed to load errors:', error);
    }
  };

  const loadServiceStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/health`);
      if (response.ok) {
        const data = await response.json();
        // Convert to our ServiceHealth format
        const formattedServices: Record<string, ServiceHealth> = {};
        Object.entries(data).forEach(([name, status]) => {
          formattedServices[name] = {
            status: status === 'healthy' ? 'healthy' : 'unhealthy',
            last_check: new Date().toISOString()
          };
        });
        setServices(formattedServices);
      }
    } catch (error) {
      console.error('Failed to load service status:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading || !isConnected) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
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
          timestamp: new Date().toISOString()
        };
        setMessages(prev => [...prev, assistantMessage]);

        // Reload history to get any queued messages
        setTimeout(loadHistory, 1000);
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

  const clearErrors = async () => {
    try {
      await fetch(`${API_BASE}/errors/clear`, { method: 'POST' });
      setErrors([]);
    } catch (error) {
      console.error('Failed to clear errors:', error);
    }
  };

  const criticalErrors = errors.filter(e => e.severity === 'critical').length;
  const warningErrors = errors.filter(e => e.severity === 'warning').length;
  const unhealthyServices = Object.values(services).filter(s => s.status === 'unhealthy').length;

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#1e1e1e'
    }}>
      {/* Header */}
      <header style={{
        height: '60px',
        background: '#2d2d30',
        borderBottom: '1px solid #3e3e42',
        padding: '0 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
        color: '#cccccc'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <h1 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>
            Memory Intelligence Chat
          </h1>

          {/* Connection status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: isConnected ? '#4ec9b0' : '#f48771'
            }} />
            <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
          </div>
        </div>

        {/* Layout controls */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => setLayout('chat-only')}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              background: layout === 'chat-only' ? '#0e639c' : '#3e3e42',
              color: '#cccccc',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer'
            }}
          >
            💬 Chat Only
          </button>
          <button
            onClick={() => setLayout('split')}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              background: layout === 'split' ? '#0e639c' : '#3e3e42',
              color: '#cccccc',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer'
            }}
          >
            ⚡ Hybrid
          </button>
          <button
            onClick={() => setLayout('terminal-only')}
            style={{
              padding: '6px 12px',
              fontSize: '13px',
              background: layout === 'terminal-only' ? '#0e639c' : '#3e3e42',
              color: '#cccccc',
              border: 'none',
              borderRadius: '3px',
              cursor: 'pointer'
            }}
          >
            🖥️ Terminal Only
          </button>
        </div>

        {/* Status indicators */}
        <div style={{ display: 'flex', gap: '12px', fontSize: '13px' }}>
          {criticalErrors > 0 && (
            <span style={{ color: '#f48771', fontWeight: 600 }}>
              🔴 {criticalErrors} Critical
            </span>
          )}
          {warningErrors > 0 && (
            <span style={{ color: '#dcdcaa' }}>
              ⚠️ {warningErrors} Warnings
            </span>
          )}
          {unhealthyServices > 0 && (
            <span style={{ color: '#f48771' }}>
              ⚠️ {unhealthyServices} Services Down
            </span>
          )}
        </div>
      </header>

      {/* Main content */}
      <main style={{
        flex: 1,
        display: 'flex',
        overflow: 'hidden',
        minHeight: 0
      }}>
        {/* Left: Chat or Terminal */}
        {(layout === 'chat-only' || layout === 'split') && (
          <div style={{
            flex: layout === 'split' ? '0 0 50%' : '1',
            display: 'flex',
            flexDirection: 'column',
            borderRight: layout === 'split' ? '1px solid #3e3e42' : 'none'
          }}>
            {/* Chat messages */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '16px',
              background: '#1e1e1e'
            }}>
              {messages.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  color: '#858585',
                  padding: '32px'
                }}>
                  <p>Start a conversation!</p>
                  <p style={{ fontSize: '13px', marginTop: '8px' }}>
                    Type a message below to begin.
                  </p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    style={{
                      marginBottom: '16px',
                      padding: '12px',
                      background: message.role === 'user'
                        ? '#0e639c'
                        : message.role === 'system'
                        ? '#5a1d1d'
                        : '#2d2d30',
                      color: '#cccccc',
                      borderRadius: '4px',
                      borderLeft: message.role === 'system' ? '3px solid #f48771' : 'none'
                    }}
                  >
                    <div style={{
                      fontSize: '11px',
                      fontWeight: 600,
                      marginBottom: '6px',
                      textTransform: 'uppercase',
                      color: message.role === 'user' ? '#ffffff' : '#858585'
                    }}>
                      {message.role}
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '14px' }}>
                      {message.content}
                    </div>
                    <div style={{
                      fontSize: '11px',
                      marginTop: '6px',
                      color: '#858585'
                    }}>
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div style={{
              padding: '16px',
              background: '#252526',
              borderTop: '1px solid #3e3e42',
              display: 'flex',
              gap: '8px',
              flexShrink: 0
            }}>
              <input
                ref={inputRef}
                type="text"
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder={isLoading ? "Processing..." : "Type a message..."}
                disabled={isLoading || !isConnected}
                style={{
                  flex: 1,
                  padding: '10px 12px',
                  background: '#3c3c3c',
                  border: '1px solid #3e3e42',
                  borderRadius: '4px',
                  fontSize: '14px',
                  color: '#cccccc',
                  outline: 'none'
                }}
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !isConnected || !inputMessage.trim()}
                style={{
                  padding: '10px 20px',
                  background: (isLoading || !isConnected || !inputMessage.trim())
                    ? '#3e3e42'
                    : '#0e639c',
                  color: (isLoading || !isConnected || !inputMessage.trim())
                    ? '#858585'
                    : '#ffffff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: (isLoading || !isConnected || !inputMessage.trim())
                    ? 'not-allowed'
                    : 'pointer',
                  fontSize: '14px',
                  fontWeight: 600
                }}
              >
                {isLoading ? '...' : 'Send'}
              </button>
            </div>
          </div>
        )}

        {/* Middle: xterm Terminal */}
        {(layout === 'terminal-only' || layout === 'split') && (
          <div style={{
            flex: layout === 'split' ? '0 0 50%' : '1',
            display: 'flex',
            flexDirection: 'column',
            background: '#1e1e1e'
          }}>
            <div style={{
              padding: '8px 16px',
              background: '#252526',
              borderBottom: '1px solid #3e3e42',
              fontSize: '12px',
              color: '#858585',
              fontWeight: 600
            }}>
              🖥️ TERMINAL OUTPUT
            </div>
            <TerminalDisplay wsUrl="ws://localhost:8765" />
          </div>
        )}

        {/* Right: Status + Error Panels */}
        <div style={{
          width: '350px',
          background: '#252526',
          borderLeft: '1px solid #3e3e42',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0
        }}>
          {/* Panel tabs */}
          <div style={{
            display: 'flex',
            borderBottom: '1px solid #3e3e42',
            background: '#2d2d30'
          }}>
            <button
              onClick={() => setRightPanel('status')}
              style={{
                flex: 1,
                padding: '12px',
                background: rightPanel === 'status' ? '#1e1e1e' : 'transparent',
                border: 'none',
                borderBottom: rightPanel === 'status' ? '2px solid #0e639c' : 'none',
                color: rightPanel === 'status' ? '#cccccc' : '#858585',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              📊 STATUS
            </button>
            <button
              onClick={() => setRightPanel('errors')}
              style={{
                flex: 1,
                padding: '12px',
                background: rightPanel === 'errors' ? '#1e1e1e' : 'transparent',
                border: 'none',
                borderBottom: rightPanel === 'errors' ? '2px solid #0e639c' : 'none',
                color: rightPanel === 'errors' ? '#cccccc' : '#858585',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              🚨 ERRORS ({errors.length})
            </button>
          </div>

          {/* Panel content */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px'
          }}>
            {rightPanel === 'status' ? (
              <div>
                <h3 style={{ fontSize: '14px', color: '#cccccc', marginBottom: '16px', marginTop: 0 }}>
                  Service Health
                </h3>
                {Object.entries(services).map(([name, health]) => (
                  <div
                    key={name}
                    style={{
                      marginBottom: '12px',
                      padding: '10px',
                      background: '#1e1e1e',
                      borderRadius: '4px',
                      borderLeft: `3px solid ${health.status === 'healthy' ? '#4ec9b0' : '#f48771'}`
                    }}
                  >
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      marginBottom: '4px'
                    }}>
                      <span style={{ fontSize: '13px', color: '#cccccc', fontWeight: 600 }}>
                        {name}
                      </span>
                      <span style={{
                        fontSize: '11px',
                        color: health.status === 'healthy' ? '#4ec9b0' : '#f48771'
                      }}>
                        {health.status === 'healthy' ? '✓ Online' : '✗ Offline'}
                      </span>
                    </div>
                    {health.last_check && (
                      <div style={{ fontSize: '11px', color: '#858585' }}>
                        {new Date(health.last_check).toLocaleTimeString()}
                      </div>
                    )}
                  </div>
                ))}
                {Object.keys(services).length === 0 && (
                  <div style={{ color: '#858585', fontSize: '13px' }}>
                    No service data available
                  </div>
                )}
              </div>
            ) : (
              <div>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '16px'
                }}>
                  <h3 style={{ fontSize: '14px', color: '#cccccc', margin: 0 }}>
                    Error Log
                  </h3>
                  {errors.length > 0 && (
                    <button
                      onClick={clearErrors}
                      style={{
                        padding: '4px 8px',
                        background: '#3e3e42',
                        color: '#cccccc',
                        border: 'none',
                        borderRadius: '3px',
                        fontSize: '11px',
                        cursor: 'pointer'
                      }}
                    >
                      Clear All
                    </button>
                  )}
                </div>
                {errors.slice().reverse().map((error) => (
                  <div
                    key={error.id}
                    style={{
                      marginBottom: '12px',
                      padding: '10px',
                      background: '#1e1e1e',
                      borderRadius: '4px',
                      borderLeft: `3px solid ${
                        error.severity === 'critical' ? '#f48771' :
                        error.severity === 'warning' ? '#dcdcaa' : '#858585'
                      }`
                    }}
                  >
                    <div style={{
                      fontSize: '11px',
                      color: error.severity === 'critical' ? '#f48771' :
                             error.severity === 'warning' ? '#dcdcaa' : '#858585',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      marginBottom: '6px'
                    }}>
                      {error.severity}
                      {error.service && ` • ${error.service}`}
                    </div>
                    <div style={{
                      fontSize: '13px',
                      color: '#cccccc',
                      marginBottom: '6px',
                      wordBreak: 'break-word'
                    }}>
                      {error.error}
                    </div>
                    {error.operation_context && (
                      <div style={{
                        fontSize: '11px',
                        color: '#858585',
                        fontFamily: 'monospace',
                        marginBottom: '4px'
                      }}>
                        {error.operation_context}
                      </div>
                    )}
                    <div style={{ fontSize: '11px', color: '#858585' }}>
                      {new Date(error.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))}
                {errors.length === 0 && (
                  <div style={{ color: '#858585', fontSize: '13px' }}>
                    No errors recorded
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
