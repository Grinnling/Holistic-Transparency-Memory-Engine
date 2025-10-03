// App.chat-only.tsx - Simple React chat interface
// Created: 2024-09-30
// Purpose: Clean chat UI based on test-simple-chat.html layout
// Connects to api_server_bridge.py for chat functionality

import React, { useState, useEffect, useRef } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

interface ServiceHealth {
  status: 'online' | 'offline' | 'degraded';
  url?: string;
  health_score?: number;
  restart_count?: number;
  dependencies?: string[];
}

interface ErrorEvent {
  id: string;
  timestamp: string;
  error: string;
  operation_context?: string;
  service?: string;
  severity: 'critical' | 'warning' | 'normal' | 'debug';
}

interface MemoryStats {
  episodic_count: number;
  working_memory_count: number;
  conversation_id: string;
  archival_failures?: number;
  archival_healthy?: boolean;
}

const API_BASE = 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [services, setServices] = useState<Record<string, ServiceHealth>>({});
  const [errors, setErrors] = useState<ErrorEvent[]>([]);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);
  const [sidebarTab, setSidebarTab] = useState<'status' | 'errors' | 'terminal'>('status');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermInstanceRef = useRef<Terminal | null>(null);

  // Load conversation history on mount
  useEffect(() => {
    loadHistory();
    checkConnection();
    loadServiceStatus();
    loadErrors();
    loadMemoryStats();

    // Poll for service status, errors, and memory stats every 5 seconds
    const interval = setInterval(() => {
      loadServiceStatus();
      loadErrors();
      loadMemoryStats();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

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

  const checkConnection = async () => {
    try {
      const response = await fetch(`${API_BASE}/health`);
      setIsConnected(response.ok);
    } catch (error) {
      setIsConnected(false);
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
    }
  };

  const loadServiceStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/services/dashboard`);
      if (response.ok) {
        const data = await response.json();
        // Transform dashboard data to service status
        const serviceStatus: Record<string, ServiceHealth> = {};

        // Dashboard returns service names as root keys (skip _summary)
        Object.entries(data).forEach(([name, info]: [string, any]) => {
          if (name !== '_summary') {
            serviceStatus[name] = {
              status: info.status === 'healthy' ? 'online' : 'offline',
              url: info.url,
              health_score: info.health_score,
              restart_count: info.restart_count,
              dependencies: info.dependencies
            };
          }
        });

        setServices(serviceStatus);
      }
    } catch (error) {
      console.error('Failed to load service status:', error);
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
        );
        setErrors(uniqueErrors);
      }
    } catch (error) {
      console.error('Failed to load errors:', error);
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

    // Add user message immediately
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

  return (
    <div style={{
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#1e1e1e'
    }}>
      {/* Header */}
      <header style={{
        height: '73px',
        background: '#252526',
        borderBottom: '1px solid #3e3e42',
        padding: '16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        <h1 style={{ fontSize: '20px', fontWeight: 'bold', color: '#cccccc' }}>
          Memory Intelligence Chat
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: isConnected ? '#10b981' : '#ef4444'
          }} />
          <span style={{ fontSize: '14px', color: '#9ca3af' }}>
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </header>

      {/* Main content */}
      <main style={{
        flex: 1,
        display: 'flex',
        overflow: 'hidden',
        minHeight: 0
      }}>
        {/* Chat area */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          padding: '16px'
        }}>
          {/* Chat container */}
          <div style={{
            height: '100%',
            background: '#252526',
            border: '1px solid #3e3e42',
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Messages area */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '16px',
              borderBottom: '1px solid #3e3e42'
            }}>
              {messages.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  color: '#6b7280',
                  padding: '32px'
                }}>
                  <p>Start a conversation!</p>
                  <p style={{ fontSize: '14px', marginTop: '8px' }}>
                    Type a message below to begin.
                  </p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    style={{
                      marginBottom: '12px',
                      padding: '12px',
                      background: message.role === 'user'
                        ? '#1e40af'
                        : message.role === 'system'
                        ? '#7f1d1d'
                        : '#2d2d30',
                      color: message.role === 'user' ? '#e0e7ff' : message.role === 'system' ? '#fecaca' : '#d1d5db',
                      borderRadius: '8px',
                      border: message.role === 'system' ? '1px solid #991b1b' : '1px solid #3e3e42'
                    }}
                  >
                    <div style={{
                      fontSize: '12px',
                      fontWeight: 600,
                      marginBottom: '4px',
                      textTransform: 'capitalize',
                      color: message.role === 'user' ? '#bfdbfe' : message.role === 'system' ? '#fca5a5' : '#9ca3af'
                    }}>
                      {message.role}
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {message.content}
                    </div>
                    <div style={{
                      fontSize: '11px',
                      marginTop: '4px',
                      opacity: 0.6
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
                  padding: '8px',
                  border: '1px solid #3e3e42',
                  borderRadius: '4px',
                  fontSize: '14px',
                  color: '#cccccc',
                  background: '#1e1e1e'
                }}
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !isConnected || !inputMessage.trim()}
                style={{
                  padding: '8px 16px',
                  background: (isLoading || !isConnected || !inputMessage.trim())
                    ? '#3e3e42'
                    : '#0e639c',
                  color: (isLoading || !isConnected || !inputMessage.trim())
                    ? '#6b7280'
                    : '#ffffff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: (isLoading || !isConnected || !inputMessage.trim())
                    ? 'not-allowed'
                    : 'pointer'
                }}
              >
                {isLoading ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        </div>

        {/* Monitoring Sidebar with Tabs */}
        <div style={{
          width: '384px',
          background: '#252526',
          borderLeft: '1px solid #3e3e42',
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column'
        }}>
          {/* Tabs */}
          <div style={{
            display: 'flex',
            borderBottom: '1px solid #3e3e42',
            flexShrink: 0
          }}>
            <button
              onClick={() => setSidebarTab('status')}
              style={{
                flex: 1,
                padding: '12px',
                background: sidebarTab === 'status' ? '#252526' : '#1e1e1e',
                border: 'none',
                borderBottom: sidebarTab === 'status' ? '2px solid #0e639c' : 'none',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: sidebarTab === 'status' ? 600 : 400,
                color: sidebarTab === 'status' ? '#cccccc' : '#6b7280'
              }}
            >
              Status
            </button>
            <button
              onClick={() => setSidebarTab('errors')}
              style={{
                flex: 1,
                padding: '12px',
                background: sidebarTab === 'errors' ? '#252526' : '#1e1e1e',
                border: 'none',
                borderBottom: sidebarTab === 'errors' ? '2px solid #0e639c' : 'none',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: sidebarTab === 'errors' ? 600 : 400,
                color: sidebarTab === 'errors' ? '#cccccc' : '#6b7280'
              }}
            >
              Errors {errors.length > 0 && `(${errors.length})`}
            </button>
            <button
              onClick={() => setSidebarTab('terminal')}
              style={{
                flex: 1,
                padding: '12px',
                background: sidebarTab === 'terminal' ? '#252526' : '#1e1e1e',
                border: 'none',
                borderBottom: sidebarTab === 'terminal' ? '2px solid #0e639c' : 'none',
                cursor: 'pointer',
                fontSize: '14px',
                fontWeight: sidebarTab === 'terminal' ? 600 : 400,
                color: sidebarTab === 'terminal' ? '#cccccc' : '#6b7280'
              }}
            >
              Terminal
            </button>
          </div>

          {/* Tab Content */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px'
          }}>
            {sidebarTab === 'status' ? (
              // Service Status Content
              <>
                <h3 style={{
                  marginBottom: '16px',
                  fontSize: '18px',
                  fontWeight: 'bold',
                  color: '#cccccc'
                }}>
                  Service Status
                </h3>

                {Object.keys(services).length === 0 ? (
                  <div style={{
                    textAlign: 'center',
                    color: '#6b7280',
                    padding: '32px 16px',
                    fontSize: '14px'
                  }}>
                    Loading service status...
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {Object.entries(services).map(([name, health]) => (
                      <div
                        key={name}
                        style={{
                          padding: '12px',
                          background: '#2d2d30',
                          borderRadius: '6px',
                          border: '1px solid #3e3e42'
                        }}
                      >
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: '6px'
                        }}>
                          <span style={{
                            fontSize: '14px',
                            fontWeight: 600,
                            textTransform: 'capitalize',
                            color: '#cccccc'
                          }}>
                            {name.replace('_', ' ')}
                          </span>
                          <div style={{
                            width: '8px',
                            height: '8px',
                            borderRadius: '50%',
                            background: health.status === 'online' ? '#10b981' : '#ef4444'
                          }} />
                        </div>

                        {health.url && (
                          <div style={{
                            fontSize: '11px',
                            color: '#858585',
                            fontFamily: 'monospace',
                            marginBottom: '4px'
                          }}>
                            {health.url}
                          </div>
                        )}

                        <div style={{
                          display: 'flex',
                          gap: '12px',
                          fontSize: '11px',
                          color: '#6b7280'
                        }}>
                          {health.health_score !== undefined && (
                            <span>Health: {health.health_score}%</span>
                          )}
                          {health.restart_count !== undefined && health.restart_count > 0 && (
                            <span style={{ color: '#f59e0b' }}>
                              Restarts: {health.restart_count}
                            </span>
                          )}
                        </div>

                        {health.dependencies && health.dependencies.length > 0 && (
                          <div style={{
                            fontSize: '10px',
                            color: '#9ca3af',
                            marginTop: '4px'
                          }}>
                            Depends: {health.dependencies.join(', ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Memory Stats Section */}
                <h3 style={{
                  marginTop: '24px',
                  marginBottom: '16px',
                  fontSize: '18px',
                  fontWeight: 'bold',
                  color: '#cccccc'
                }}>
                  Memory System
                </h3>

                {memoryStats ? (
                  <div style={{
                    padding: '12px',
                    background: '#2d2d30',
                    borderRadius: '6px',
                    border: '1px solid #3e3e42',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px'
                  }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '13px',
                      color: '#cccccc'
                    }}>
                      <span>Episodic Memories:</span>
                      <span style={{ fontWeight: 600, color: '#3b82f6' }}>
                        {memoryStats.episodic_count}
                      </span>
                    </div>

                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '13px',
                      color: '#cccccc'
                    }}>
                      <span>Working Memory:</span>
                      <span style={{ fontWeight: 600, color: '#10b981' }}>
                        {memoryStats.working_memory_count} messages
                      </span>
                    </div>

                    {memoryStats.archival_healthy !== undefined && (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '12px',
                        marginTop: '4px',
                        padding: '6px 8px',
                        background: memoryStats.archival_healthy ? '#10b98120' : '#ef444420',
                        borderRadius: '4px',
                        color: memoryStats.archival_healthy ? '#10b981' : '#ef4444'
                      }}>
                        <div style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          background: memoryStats.archival_healthy ? '#10b981' : '#ef4444'
                        }} />
                        <span>
                          {memoryStats.archival_healthy
                            ? 'Archival Healthy'
                            : `Archival Issues (${memoryStats.archival_failures || 0} failures)`}
                        </span>
                      </div>
                    )}

                    <div style={{
                      fontSize: '10px',
                      color: '#6b7280',
                      marginTop: '4px',
                      fontFamily: 'monospace'
                    }}>
                      Session: {memoryStats.conversation_id.slice(0, 8)}...
                    </div>
                  </div>
                ) : (
                  <div style={{
                    textAlign: 'center',
                    color: '#6b7280',
                    padding: '16px',
                    fontSize: '14px'
                  }}>
                    Loading memory stats...
                  </div>
                )}
              </>
            ) : sidebarTab === 'errors' ? (
              // Error Panel Content
              <>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: '16px'
                }}>
                  <h3 style={{
                    fontSize: '18px',
                    fontWeight: 'bold',
                    color: '#cccccc',
                    margin: 0
                  }}>
                    Error Log
                  </h3>
                  {errors.length > 0 && (
                    <button
                      onClick={async () => {
                        try {
                          await fetch(`${API_BASE}/errors/clear`, { method: 'POST' });
                          setErrors([]);
                        } catch (error) {
                          console.error('Failed to clear errors:', error);
                        }
                      }}
                      style={{
                        padding: '6px 12px',
                        background: '#3e3e42',
                        color: '#cccccc',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '12px',
                        fontWeight: 500
                      }}
                    >
                      Clear All
                    </button>
                  )}
                </div>

                {errors.length === 0 ? (
                  <div style={{
                    textAlign: 'center',
                    color: '#6b7280',
                    padding: '32px 16px',
                    fontSize: '14px'
                  }}>
                    No errors detected
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {errors.map((error) => (
                      <div
                        key={error.id}
                        style={{
                          padding: '12px',
                          background: error.severity === 'critical' ? '#3a1a1a' :
                                     error.severity === 'warning' ? '#3a2e1a' :
                                     error.severity === 'debug' ? '#1e1e1e' : '#2d2d30',
                          borderRadius: '6px',
                          border: `1px solid ${
                            error.severity === 'critical' ? '#7f1d1d' :
                            error.severity === 'warning' ? '#92400e' :
                            '#3e3e42'
                          }`
                        }}
                      >
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          marginBottom: '6px'
                        }}>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            textTransform: 'uppercase',
                            color: error.severity === 'critical' ? '#ef4444' :
                                   error.severity === 'warning' ? '#f59e0b' :
                                   '#858585'
                          }}>
                            {error.severity}
                          </span>
                          {error.service && (
                            <span style={{
                              fontSize: '10px',
                              color: '#858585',
                              fontFamily: 'monospace'
                            }}>
                              {error.service}
                            </span>
                          )}
                        </div>

                        <div style={{
                          fontSize: '13px',
                          color: '#d1d5db',
                          marginBottom: '6px',
                          wordBreak: 'break-word'
                        }}>
                          {error.error}
                        </div>

                        {error.operation_context && (
                          <div style={{
                            fontSize: '11px',
                            color: '#858585',
                            marginBottom: '4px'
                          }}>
                            Context: {error.operation_context}
                          </div>
                        )}

                        <div style={{
                          fontSize: '10px',
                          color: '#6b7280'
                        }}>
                          {new Date(error.timestamp).toLocaleString()}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              // Terminal Panel Content
              <>
                <h3 style={{
                  marginBottom: '16px',
                  fontSize: '18px',
                  fontWeight: 'bold',
                  color: '#cccccc'
                }}>
                  Terminal
                </h3>
                <div
                  ref={terminalRef}
                  style={{
                    height: 'calc(100% - 40px)',
                    background: '#000000',
                    borderRadius: '4px',
                    padding: '8px'
                  }}
                />
              </>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
