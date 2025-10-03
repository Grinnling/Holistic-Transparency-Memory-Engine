// App.chat-only.tsx - Simple React chat interface
// Created: 2024-09-30
// Purpose: Clean chat UI based on test-simple-chat.html layout
// Connects to api_server_bridge.py for chat functionality

import React, { useState, useEffect, useRef } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

const API_BASE = 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load conversation history on mount
  useEffect(() => {
    loadHistory();
    checkConnection();
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
      background: '#f9fafb'
    }}>
      {/* Header */}
      <header style={{
        height: '73px',
        background: 'white',
        borderBottom: '1px solid #e5e7eb',
        padding: '16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        <h1 style={{ fontSize: '20px', fontWeight: 'bold' }}>
          Memory Intelligence Chat
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: isConnected ? '#10b981' : '#ef4444'
          }} />
          <span style={{ fontSize: '14px', color: '#6b7280' }}>
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
            background: 'white',
            border: '1px solid #e5e7eb',
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column'
          }}>
            {/* Messages area */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '16px',
              borderBottom: '1px solid #e5e7eb'
            }}>
              {messages.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  color: '#9ca3af',
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
                        ? '#3b82f6'
                        : message.role === 'system'
                        ? '#fef2f2'
                        : '#f3f4f6',
                      color: message.role === 'user' ? 'white' : '#1f2937',
                      borderRadius: '8px',
                      border: message.role === 'system' ? '1px solid #fecaca' : 'none'
                    }}
                  >
                    <div style={{
                      fontSize: '12px',
                      fontWeight: 600,
                      marginBottom: '4px',
                      textTransform: 'capitalize'
                    }}>
                      {message.role}
                    </div>
                    <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                      {message.content}
                    </div>
                    <div style={{
                      fontSize: '11px',
                      marginTop: '4px',
                      opacity: 0.7
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
                  border: '1px solid #d1d5db',
                  borderRadius: '4px',
                  fontSize: '14px'
                }}
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !isConnected || !inputMessage.trim()}
                style={{
                  padding: '8px 16px',
                  background: (isLoading || !isConnected || !inputMessage.trim())
                    ? '#9ca3af'
                    : '#3b82f6',
                  color: 'white',
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

        {/* Sidebar placeholder for future error panel */}
        <div style={{
          width: '384px',
          background: 'white',
          borderLeft: '1px solid #e5e7eb',
          padding: '16px',
          flexShrink: 0
        }}>
          <h3 style={{ marginBottom: '8px' }}>Status Panel</h3>
          <p style={{ fontSize: '14px', color: '#6b7280' }}>
            Service status and errors will appear here
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;
