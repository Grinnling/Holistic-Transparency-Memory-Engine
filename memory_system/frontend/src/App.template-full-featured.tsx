// App.tsx - Main React application
import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Badge } from './components/ui/badge';
import { Textarea } from './components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { ScrollArea } from './components/ui/scroll-area';
import { Separator } from './components/ui/separator';
import ErrorPanel from './components/ErrorPanel';
import ServiceStatusPanel from './components/ServiceStatusPanel';
import FileUploadPanel from './components/FileUploadPanel';
// import ConversationList from './components/ConversationList'; // For future branching feature
import { 
  Send, 
  Settings, 
  MessageSquare, 
  Upload, 
  Monitor,
  AlertCircle,
  User,
  Bot,
  Clock
} from 'lucide-react';

// Types (matches our WebSocket message types)
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  confidence_score?: number;
  operation_context?: string;
  citations?: Citation[];
}

interface Citation {
  source: string;
  content: string;
  relevance_score: number;
  type: 'memory' | 'document' | 'web' | 'code' | 'episodic';
}

interface ErrorEvent {
  id: string;
  timestamp: string;
  error: string;
  severity: 'critical' | 'warning' | 'normal' | 'debug';
  operation_context?: string;
  service?: string;
  attempted_fixes: string[];
  fix_success?: boolean;
  user_impact: 'blocking' | 'degraded' | 'minimal' | 'none';
}

interface ServiceStatus {
  [serviceName: string]: {
    status: 'healthy' | 'unhealthy' | 'degraded' | 'starting' | 'stopped';
    latency?: number;
    last_check: string;
    error_count?: number;
  };
}

const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

const App: React.FC = () => {
  // Core state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  // Error and service monitoring (what Claude needs!)
  const [errors, setErrors] = useState<ErrorEvent[]>([]);
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus>({});
  const [conversationId, setConversationId] = useState<string>('');
  
  // UI state
  const [activeTab, setActiveTab] = useState('chat');
  const [showSettings, setShowSettings] = useState(false);
  
  // Refs
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // WebSocket connection
  useEffect(() => {
    connectWebSocket();
    loadInitialData();
    
    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const connectWebSocket = () => {
    try {
      const ws = new WebSocket(WS_URL);
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        // Auto-reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };
      
      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
      setIsConnected(false);
    }
  };

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'chat_update':
        if (data.message) {
          setMessages(prev => [...prev, data.message]);
        }
        break;
        
      case 'error_event':
        if (data.error) {
          setErrors(prev => [...prev, data.error]);
        }
        break;
        
      case 'service_status':
        if (data.services) {
          setServiceStatus(data.services);
        }
        break;
        
      case 'connection_established':
        setConversationId(data.conversation_id || '');
        break;
        
      default:
        console.log('Unknown WebSocket message:', data);
    }
  };

  const loadInitialData = async () => {
    try {
      // Load conversation history
      const historyResponse = await fetch(`${API_BASE}/history`);
      if (historyResponse.ok) {
        const historyData = await historyResponse.json();
        if (historyData.history) {
          const formattedMessages: ChatMessage[] = historyData.history.map((exchange: any, index: number) => [
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
              confidence_score: exchange.validation?.confidence_score
            }
          ]).flat();
          setMessages(formattedMessages);
        }
      }

      // Load service status
      const healthResponse = await fetch(`${API_BASE}/health`);
      if (healthResponse.ok) {
        const healthData = await healthResponse.json();
        const formattedStatus: ServiceStatus = {};
        Object.entries(healthData).forEach(([service, status]) => {
          formattedStatus[service] = {
            status: status === 'healthy' ? 'healthy' : 'unhealthy',
            last_check: new Date().toISOString()
          };
        });
        setServiceStatus(formattedStatus);
      }

      // Load existing errors
      const errorsResponse = await fetch(`${API_BASE}/errors`);
      if (errorsResponse.ok) {
        const errorsData = await errorsResponse.json();
        setErrors([...errorsData.session, ...errorsData.recent]);
      }

    } catch (error) {
      console.error('Failed to load initial data:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date().toISOString()
    };

    // Add user message immediately
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: inputMessage.trim() })
      });

      if (response.ok) {
        const data = await response.json();
        const assistantMessage: ChatMessage = {
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content: data.response,
          timestamp: new Date().toISOString(),
          confidence_score: data.confidence_score,
          operation_context: data.operation_context
        };
        
        setMessages(prev => [...prev, assistantMessage]);
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      
      // Add error message
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Failed to send message: ${error}`,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      setInputMessage('');
      inputRef.current?.focus();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const acknowledgeError = async (errorId: string) => {
    try {
      await fetch(`${API_BASE}/errors/${errorId}/acknowledge`, {
        method: 'POST'
      });
      setErrors(prev => 
        prev.map(error => 
          error.id === errorId 
            ? { ...error, acknowledged: true }
            : error
        )
      );
    } catch (error) {
      console.error('Failed to acknowledge error:', error);
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

  const reportFixResult = async (errorId: string, worked: boolean) => {
    // Update the error locally
    setErrors(prev =>
      prev.map(error =>
        error.id === errorId
          ? { ...error, fix_success: worked }
          : error
      )
    );
    
    // TODO: Send to backend when endpoint is available
    console.log(`Fix for ${errorId} ${worked ? 'worked' : 'failed'}`);
  };

  const getMessageIcon = (role: string) => {
    switch (role) {
      case 'user': return <User className="h-4 w-4" />;
      case 'assistant': return <Bot className="h-4 w-4" />;
      case 'system': return <AlertCircle className="h-4 w-4" />;
      default: return <MessageSquare className="h-4 w-4" />;
    }
  };

  const getConfidenceColor = (score?: number) => {
    if (!score) return 'text-gray-500';
    if (score >= 0.8) return 'text-green-600';
    if (score >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const criticalErrors = errors.filter(e => e.severity === 'critical').length;
  const warningErrors = errors.filter(e => e.severity === 'warning').length;

  return (
    <div className="h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold">Memory Intelligence Chat</h1>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-600">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {criticalErrors > 0 && (
            <Badge variant="destructive" className="animate-pulse">
              {criticalErrors} Critical
            </Badge>
          )}
          {warningErrors > 0 && (
            <Badge variant="secondary">
              {warningErrors} Warning
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSettings(!showSettings)}
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Main chat area */}
        <div className="flex-1 flex flex-col">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
            <TabsList className="m-4 mb-0 w-fit">
              <TabsTrigger value="chat" className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Chat
              </TabsTrigger>
              <TabsTrigger value="files" className="flex items-center gap-2">
                <Upload className="h-4 w-4" />
                Files
              </TabsTrigger>
            </TabsList>

            <TabsContent value="chat" className="flex-1 flex flex-col m-4 mt-2">
              <Card className="flex-1 flex flex-col">
                <CardHeader className="pb-2">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <MessageSquare className="h-5 w-5" />
                    Conversation
                    {conversationId && (
                      <span className="text-xs font-normal text-gray-500 ml-2">
                        ID: {conversationId.slice(0, 8)}...
                      </span>
                    )}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 flex flex-col p-0">
                  {/* Messages area */}
                  <ScrollArea className="flex-1 p-4">
                    <div className="space-y-4">
                      {messages.length === 0 ? (
                        <div className="text-center text-gray-500 py-8">
                          <Bot className="h-12 w-12 mx-auto mb-4 text-gray-300" />
                          <p>Start a conversation!</p>
                          <p className="text-sm mt-2">I can help with memory queries, code analysis, and more.</p>
                        </div>
                      ) : (
                        messages.map((message) => (
                          <div
                            key={message.id}
                            className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                          >
                            <div
                              className={`max-w-[80%] rounded-lg p-3 ${
                                message.role === 'user'
                                  ? 'bg-blue-600 text-white ml-12'
                                  : message.role === 'system'
                                  ? 'bg-red-100 border border-red-200'
                                  : 'bg-gray-100 border border-gray-200 mr-12'
                              }`}
                            >
                              <div className="flex items-start gap-2 mb-2">
                                {getMessageIcon(message.role)}
                                <span className="text-sm font-medium capitalize">
                                  {message.role}
                                </span>
                                {message.confidence_score && (
                                  <span className={`text-xs ${getConfidenceColor(message.confidence_score)}`}>
                                    {Math.round(message.confidence_score * 100)}% confidence
                                  </span>
                                )}
                                <span className="text-xs text-gray-500 ml-auto flex items-center gap-1">
                                  <Clock className="h-3 w-3" />
                                  {new Date(message.timestamp).toLocaleTimeString()}
                                </span>
                              </div>
                              
                              <div className="whitespace-pre-wrap break-words">
                                {message.content}
                              </div>
                              
                              {message.operation_context && (
                                <div className="text-xs text-gray-500 mt-2 font-mono bg-gray-50 p-1 rounded">
                                  Context: {message.operation_context}
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                      <div ref={messagesEndRef} />
                    </div>
                  </ScrollArea>

                  <Separator />

                  {/* Input area */}
                  <div className="p-4">
                    <div className="flex gap-2 items-end">
                      <Textarea
                        ref={inputRef}
                        value={inputMessage}
                        onChange={(e) => setInputMessage(e.target.value)}
                        onKeyDown={handleKeyPress}
                        placeholder={isLoading ? "Processing..." : "Type your message... (Enter to send, Shift+Enter for new line)"}
                        disabled={isLoading || !isConnected}
                        className="flex-1 min-h-[60px] max-h-[200px] resize-none"
                        rows={2}
                      />
                      <Button
                        onClick={sendMessage}
                        disabled={isLoading || !isConnected || !inputMessage.trim()}
                        className="h-[60px]"
                      >
                        <Send className="h-4 w-4" />
                      </Button>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">
                      Press Enter to send, Shift+Enter for new line
                    </p>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="files" className="flex-1 m-4 mt-2">
              <FileUploadPanel />
            </TabsContent>
          </Tabs>
        </div>

        {/* Right sidebar */}
        <div className="w-96 border-l border-gray-200 bg-white flex flex-col">
          <Tabs defaultValue="status" className="flex-1 flex flex-col">
            <TabsList className="m-4 mb-2 w-full">
              <TabsTrigger value="status" className="flex-1">
                <Monitor className="h-4 w-4 mr-1" />
                Status
              </TabsTrigger>
              <TabsTrigger value="errors" className="flex-1">
                <AlertCircle className="h-4 w-4 mr-1" />
                Errors {errors.length > 0 && `(${errors.length})`}
              </TabsTrigger>
            </TabsList>

            <div className="flex-1 overflow-hidden">
              <TabsContent value="status" className="h-full m-4 mt-2">
                <ServiceStatusPanel 
                  services={serviceStatus}
                  conversationId={conversationId}
                />
              </TabsContent>

              <TabsContent value="errors" className="h-full m-4 mt-2">
                <ErrorPanel
                  errors={errors}
                  onAcknowledge={acknowledgeError}
                  onClear={clearErrors}
                  onReportFix={reportFixResult}
                />
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </div>
    </div>
  );
};

export default App;