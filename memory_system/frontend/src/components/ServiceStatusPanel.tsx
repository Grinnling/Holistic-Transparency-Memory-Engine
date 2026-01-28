// components/ServiceStatusPanel.tsx
// Real-time service health monitoring panel with LLM status and admin controls

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { useToast } from '../contexts/ToastContext';
import { reportCaughtError } from '../utils/errorReporter';
import {
  Activity,
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Power,
  Clock,
  Zap,
  Database,
  Brain,
  FileText,
  Archive,
  Cpu,
  RotateCcw,
  PowerOff,
  Plug,
  Wifi,
  WifiOff
} from 'lucide-react';

interface ServiceInfo {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'starting' | 'stopped' | 'offline';
  latency?: number;
  last_check: string;
  error_count?: number;
}

interface LLMModelStatus {
  status: string;
  model?: string | null;
  provider?: string | null;
  endpoint?: string;
  note?: string;
}

interface LLMStatus {
  chat: LLMModelStatus;
  embedding: LLMModelStatus;
  rerank: LLMModelStatus;
  lmstudio_models: string[];
  lmstudio_error?: string;
}

interface ServiceStatusPanelProps {
  services: { [serviceName: string]: ServiceInfo };
  conversationId?: string;
  onServiceAction?: (service: string, action: 'start' | 'stop' | 'restart') => void;
}

const API_BASE = 'http://localhost:8000';

const ServiceStatusPanel: React.FC<ServiceStatusPanelProps> = ({
  services,
  conversationId,
  onServiceAction
}) => {
  const toast = useToast();

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedServices, setExpandedServices] = useState<Set<string>>(new Set());
  const [autoRefresh, setAutoRefresh] = useState(true);

  // LLM Status state
  const [llmStatus, setLlmStatus] = useState<LLMStatus | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);

  // Admin action state
  const [adminLoading, setAdminLoading] = useState<string | null>(null);
  const [adminMessage, setAdminMessage] = useState<string | null>(null);

  // Connection state for auto-reconnect
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'reconnecting'>('connected');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const reconnectAttemptsRef = useRef(0);  // Ref for accurate count capture (state is async)
  const wasDisconnected = useRef(false);

  // Ref for synchronous click protection (prevents rapid double-clicks)
  const adminActionInProgress = useRef(false);
  const lastActionTime = useRef(0);
  const ACTION_COOLDOWN_MS = 1000; // Minimum time between actions

  // Toggle service expansion (allows multiple)
  const toggleService = (serviceName: string) => {
    setExpandedServices(prev => {
      const next = new Set(prev);
      if (next.has(serviceName)) {
        next.delete(serviceName);
      } else {
        next.add(serviceName);
      }
      return next;
    });
  };

  // Fetch LLM status with connection tracking
  const fetchLLMStatus = async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/llm/status`, {
        signal: AbortSignal.timeout(5000)
      });
      if (response.ok) {
        const data = await response.json();
        setLlmStatus(data);

        // If we were disconnected, we're now reconnected
        if (wasDisconnected.current) {
          // Capture attempt count from ref (state is async, ref is accurate)
          const attempts = reconnectAttemptsRef.current;

          setConnectionStatus('connected');
          setReconnectAttempts(0);
          reconnectAttemptsRef.current = 0;  // Reset ref too
          wasDisconnected.current = false;
          setAdminMessage(null);  // Clear any stuck admin messages
          toast.success('API reconnected');
          console.log(`API reconnected after ${attempts} attempts`);

          // Report recovery to ErrorHandler
          reportCaughtError(
            new Error(`LLM API reconnected after ${attempts} attempts`),
            'ServiceStatusPanel',
            'fetchLLMStatus:recovery',
            {
              context: `reconnect_attempts: ${attempts}`,
              severity: 'low'  // Recovery is good news
            }
          );
        }
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to fetch LLM status:', error);

      // Mark as disconnected - only report once on first disconnect
      if (connectionStatus === 'connected') {
        setConnectionStatus('disconnected');
        wasDisconnected.current = true;
        toast.warning('API disconnected - attempting to reconnect...');
        console.log('API disconnected - starting reconnect polling');

        // Report to ErrorHandler (only on initial disconnect, not during polling)
        reportCaughtError(error, 'ServiceStatusPanel', 'fetchLLMStatus', {
          context: 'Initial disconnect detected',
          severity: 'low'  // Low because auto-reconnect handles this
        });
      }
      return false;
    }
  };

  // Auto-refresh when connected (every 5 seconds)
  useEffect(() => {
    if (connectionStatus !== 'connected') return;

    fetchLLMStatus();
    if (autoRefresh) {
      const interval = setInterval(() => {
        setIsRefreshing(true);
        fetchLLMStatus();
        setTimeout(() => setIsRefreshing(false), 500);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, connectionStatus]);

  // Reconnect polling when disconnected (every 2 seconds)
  useEffect(() => {
    if (connectionStatus === 'connected') return;

    setConnectionStatus('reconnecting');

    const reconnectInterval = setInterval(async () => {
      reconnectAttemptsRef.current++;  // Ref for accurate capture
      setReconnectAttempts(prev => prev + 1);  // State for display
      const success = await fetchLLMStatus();

      if (success) {
        // Reconnected - this will trigger the connected useEffect
        clearInterval(reconnectInterval);
      }
    }, 2000);

    return () => clearInterval(reconnectInterval);
  }, [connectionStatus]);

  // Admin action handlers with synchronous click protection + cooldown
  const handleReconnectLLM = async () => {
    // Synchronous guard with cooldown - prevents rapid clicks
    const now = Date.now();
    if (adminActionInProgress.current || (now - lastActionTime.current) < ACTION_COOLDOWN_MS) return;
    adminActionInProgress.current = true;
    lastActionTime.current = now;

    setAdminLoading('reconnect');
    setAdminMessage(null);
    try {
      const response = await fetch(`${API_BASE}/llm/reconnect`, { method: 'POST' });
      const data = await response.json();
      setAdminMessage(data.message);
      if (data.success) {
        toast.success('LLM reconnected successfully');
        fetchLLMStatus();
      } else {
        toast.error(data.message || 'Failed to reconnect LLM');
      }
    } catch (error) {
      setAdminMessage('Failed to reconnect LLM');
      toast.error('Failed to reconnect LLM');
      reportCaughtError(error, 'ServiceStatusPanel', 'handleReconnectLLM', {
        context: 'Admin action: reconnect LLM',
        severity: 'medium'
      });
    }
    setAdminLoading(null);
    adminActionInProgress.current = false;
  };

  const handleShutdownAPI = async () => {
    if (!confirm('Shut down the API server? The UI will disconnect.')) return;
    // Synchronous guard with cooldown
    const now = Date.now();
    if (adminActionInProgress.current || (now - lastActionTime.current) < ACTION_COOLDOWN_MS) return;
    adminActionInProgress.current = true;
    lastActionTime.current = now;

    setAdminLoading('shutdown');
    setAdminMessage(null);
    try {
      await fetch(`${API_BASE}/services/shutdown`, { method: 'POST' });
      setAdminMessage('API shutting down...');
      toast.warning('API shutting down...');
    } catch (error) {
      setAdminMessage('Shutdown request sent');
      toast.info('Shutdown request sent');
    }
    setAdminLoading(null);
    adminActionInProgress.current = false;
  };

  const handleClusterRestart = async () => {
    if (!confirm('Full cluster restart? All services will stop and restart. This may take a moment.')) return;
    // Synchronous guard with cooldown
    const now = Date.now();
    if (adminActionInProgress.current || (now - lastActionTime.current) < ACTION_COOLDOWN_MS) return;
    adminActionInProgress.current = true;
    lastActionTime.current = now;

    setAdminLoading('restart');
    setAdminMessage(null);
    try {
      const response = await fetch(`${API_BASE}/services/cluster-restart`, { method: 'POST' });
      const data = await response.json();
      setAdminMessage(data.message);
      if (data.success) {
        toast.info('Cluster restart initiated - services will restart momentarily');
      } else {
        toast.error(data.message || 'Cluster restart failed');
      }
    } catch (error) {
      setAdminMessage('Restart request sent');
      toast.info('Restart request sent');
    }
    setAdminLoading(null);
    adminActionInProgress.current = false;
  };

  const getServiceIcon = (serviceName: string) => {
    const icons: { [key: string]: React.ReactNode } = {
      // Core memory services
      'working_memory': <Brain className="h-4 w-4" />,
      'episodic_memory': <Archive className="h-4 w-4" />,
      // Validation/logging
      'curator': <FileText className="h-4 w-4" />,
      'mcp_logger': <Database className="h-4 w-4" />,
      // Storage services
      'redis': <Database className="h-4 w-4" />,
      'sqlite': <Database className="h-4 w-4" />,
      'yarnboard': <Activity className="h-4 w-4" />,
      'scratchpad': <FileText className="h-4 w-4" />,
      // Additional services
      'ozolith': <Archive className="h-4 w-4" />,
      'llm': <Brain className="h-4 w-4" />,
      'skinflap': <AlertCircle className="h-4 w-4" />,
    };
    return icons[serviceName] || <Activity className="h-4 w-4" />;
  };

  // Color scheme: grey=OK, blue=suspicious/uncertain, red=bad
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'connected':
      case 'available':
        return <CheckCircle className="h-4 w-4 text-gray-400" />;  // Grey = OK
      case 'degraded':
      case 'starting':
      case 'disconnected':
        return <AlertCircle className="h-4 w-4 text-blue-400" />;  // Blue = uncertain
      case 'unhealthy':
      case 'stopped':
      case 'offline':
        return <AlertCircle className="h-4 w-4 text-red-400" />;   // Red = bad
      case 'not_configured':
        return <Activity className="h-4 w-4 text-gray-600" />;     // Dimmed
      default:
        return <Activity className="h-4 w-4 text-gray-500" />;
    }
  };

  // Dark theme colors: grey=OK, blue=suspicious/uncertain, red=bad
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'connected':
      case 'available':
        return 'bg-gray-700 text-gray-200 border-gray-600';        // Grey = OK
      case 'degraded':
      case 'starting':
      case 'disconnected':
        return 'bg-blue-900 text-blue-200 border-blue-800';        // Blue = uncertain
      case 'unhealthy':
      case 'stopped':
      case 'offline':
        return 'bg-red-900 text-red-200 border-red-800';           // Red = bad
      case 'not_configured':
        return 'bg-gray-800 text-gray-500 border-gray-700';        // Dimmed
      default:
        return 'bg-gray-800 text-gray-300 border-gray-700';
    }
  };

  const getHealthScore = () => {
    const serviceList = Object.values(services);
    if (serviceList.length === 0) return 0;

    const healthyCount = serviceList.filter(s => s.status === 'healthy').length;
    return Math.round((healthyCount / serviceList.length) * 100);
  };

  // Latency: grey=fast, blue=medium, red=slow
  const getLatencyColor = (latency?: number) => {
    if (latency == null) return 'text-gray-400';  // null or undefined
    if (latency < 100) return 'text-gray-300';    // Grey = good (includes 0)
    if (latency < 300) return 'text-blue-400';    // Blue = suspicious
    return 'text-red-400';                         // Red = bad
  };

  const formatLatency = (latency?: number) => {
    if (latency == null) return 'N/A';  // null or undefined, but NOT 0
    if (latency < 1000) return `${latency}ms`;
    return `${(latency / 1000).toFixed(2)}s`;
  };

  const formatLastCheck = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return date.toLocaleDateString();
  };

  const healthScore = getHealthScore();
  const criticalServices = Object.entries(services).filter(
    ([_, info]) => info.status === 'unhealthy' || info.status === 'stopped'
  );

  return (
    <div className="space-y-4">
      {/* Connection Status Banner */}
      {connectionStatus !== 'connected' && (
        <div className="p-3 bg-yellow-900/50 border border-yellow-700 rounded-lg flex items-center gap-3">
          <WifiOff className="h-5 w-5 text-yellow-400 animate-pulse" />
          <div className="flex-1">
            <div className="text-sm font-medium text-yellow-200">
              {connectionStatus === 'reconnecting' ? 'Reconnecting to API...' : 'API Disconnected'}
            </div>
            <div className="text-xs text-yellow-400">
              Attempt {reconnectAttempts} - checking every 2 seconds
            </div>
          </div>
          <RefreshCw className="h-4 w-4 text-yellow-400 animate-spin" />
        </div>
      )}

      {/* Overall Health */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setAutoRefresh(!autoRefresh)}
                className="h-8 px-2"
              >
                <RefreshCw className={`h-4 w-4 ${autoRefresh ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">
                Overall Score
                {isRefreshing && (
                  <span className="ml-2 text-xs text-blue-400 animate-pulse">
                    updating...
                  </span>
                )}
              </span>
              <span className={`text-lg font-bold transition-opacity ${
                isRefreshing ? 'opacity-50' : 'opacity-100'
              } ${
                healthScore >= 75 ? 'text-gray-300' :    // Grey = OK
                healthScore >= 50 ? 'text-blue-400' :    // Blue = suspicious
                'text-red-400'                            // Red = bad
              }`}>
                {healthScore}%
              </span>
            </div>
            <Progress
              value={healthScore}
              className={`h-2 transition-opacity ${isRefreshing ? 'opacity-50' : 'opacity-100'}`}
            />

            {criticalServices.length > 0 && (
              <div className="mt-2 p-2 bg-red-900/50 border border-red-800 rounded text-xs">
                <div className="flex items-center gap-1 text-red-300">
                  <AlertCircle className="h-3 w-3" />
                  <span className="font-medium">Critical Issues:</span>
                </div>
                {criticalServices.map(([name]) => (
                  <div key={name} className="ml-4 text-red-400">• {name}</div>
                ))}
              </div>
            )}

            {conversationId && (
              <div className="mt-2 text-xs text-gray-500">
                <span className="font-medium">Session:</span> {conversationId.slice(0, 8)}...
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* LLM Status Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Cpu className="h-4 w-4" />
              LLM Status
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchLLMStatus}
              disabled={llmLoading}
              className="h-7 px-2"
            >
              <RefreshCw className={`h-3 w-3 ${llmLoading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {llmStatus ? (
            <>
              {/* Chat Model */}
              <div className={`p-2 rounded border ${getStatusColor(llmStatus.chat.status)}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Brain className="h-3 w-3" />
                    <span className="text-xs font-medium">Chat</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(llmStatus.chat.status)}
                    <Badge variant="secondary" className={`text-[10px] ${getStatusColor(llmStatus.chat.status)}`}>
                      {llmStatus.chat.status}
                    </Badge>
                  </div>
                </div>
                {llmStatus.chat.model && (
                  <div className="mt-1 text-[10px] text-gray-400 truncate" title={llmStatus.chat.model}>
                    {llmStatus.chat.model}
                  </div>
                )}
                {llmStatus.chat.provider && (
                  <div className="text-[10px] text-gray-500">
                    via {llmStatus.chat.provider}
                  </div>
                )}
              </div>

              {/* Embedding Model */}
              <div className={`p-2 rounded border ${getStatusColor(llmStatus.embedding.status)}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="h-3 w-3" />
                    <span className="text-xs font-medium">Embedding</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(llmStatus.embedding.status)}
                    <Badge variant="secondary" className={`text-[10px] ${getStatusColor(llmStatus.embedding.status)}`}>
                      {llmStatus.embedding.status}
                    </Badge>
                  </div>
                </div>
                {llmStatus.embedding.model && (
                  <div className="mt-1 text-[10px] text-gray-400 truncate" title={llmStatus.embedding.model}>
                    {llmStatus.embedding.model}
                  </div>
                )}
              </div>

              {/* Rerank Model */}
              <div className={`p-2 rounded border ${getStatusColor(llmStatus.rerank.status)}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Activity className="h-3 w-3" />
                    <span className="text-xs font-medium">Rerank</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(llmStatus.rerank.status)}
                    <Badge variant="secondary" className={`text-[10px] ${getStatusColor(llmStatus.rerank.status)}`}>
                      {llmStatus.rerank.status}
                    </Badge>
                  </div>
                </div>
                {llmStatus.rerank.model ? (
                  <div className="mt-1 text-[10px] text-gray-400 truncate" title={llmStatus.rerank.model}>
                    {llmStatus.rerank.model}
                  </div>
                ) : llmStatus.rerank.note && (
                  <div className="mt-1 text-[10px] text-gray-500 italic">
                    {llmStatus.rerank.note}
                  </div>
                )}
              </div>

              {/* Loaded Models List */}
              {llmStatus.lmstudio_models.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-700">
                  <div className="text-[10px] text-gray-500 mb-1">LM Studio loaded models:</div>
                  <div className="text-[10px] text-gray-400 space-y-0.5">
                    {llmStatus.lmstudio_models.map((model, i) => (
                      <div key={i} className="truncate" title={model}>• {model}</div>
                    ))}
                  </div>
                </div>
              )}

              {llmStatus.lmstudio_error && (
                <div className="mt-2 p-2 bg-red-900/30 border border-red-800 rounded text-[10px] text-red-400">
                  LM Studio error: {llmStatus.lmstudio_error}
                </div>
              )}
            </>
          ) : (
            <div className="text-center text-gray-500 py-2 text-xs">
              Loading LLM status...
            </div>
          )}
        </CardContent>
      </Card>

      {/* Admin Controls */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Power className="h-4 w-4" />
            Admin Controls
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid grid-cols-1 gap-2">
            {/* Reconnect LLM */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleReconnectLLM}
              disabled={adminLoading !== null}
              className="w-full justify-start h-8 text-xs"
            >
              <Plug className="h-3 w-3 mr-2" />
              {adminLoading === 'reconnect' ? 'Reconnecting...' : 'Reconnect LLM'}
            </Button>

            {/* Shutdown API */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleShutdownAPI}
              disabled={adminLoading !== null}
              className="w-full justify-start h-8 text-xs text-yellow-500 hover:text-yellow-400 border-yellow-700 hover:border-yellow-600"
            >
              <PowerOff className="h-3 w-3 mr-2" />
              {adminLoading === 'shutdown' ? 'Shutting down...' : 'Shutdown API'}
            </Button>

            {/* Cluster Restart */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleClusterRestart}
              disabled={adminLoading !== null}
              className="w-full justify-start h-8 text-xs text-red-500 hover:text-red-400 border-red-700 hover:border-red-600"
            >
              <RotateCcw className="h-3 w-3 mr-2" />
              {adminLoading === 'restart' ? 'Restarting...' : 'Full Cluster Restart'}
            </Button>
          </div>

          {/* Status Message */}
          {adminMessage && (
            <div className="mt-2 p-2 bg-gray-800 border border-gray-700 rounded text-xs text-gray-300">
              {adminMessage}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Individual Services */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium">Service Status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {Object.keys(services).length === 0 ? (
            <div className="text-center text-gray-500 py-4 text-sm">
              No services detected
            </div>
          ) : (
            Object.entries(services).map(([serviceName, info]) => (
              <div
                key={serviceName}
                className={`p-3 rounded-lg border transition-all cursor-pointer ${
                  expandedServices.has(serviceName) ? 'ring-2 ring-blue-500' : ''
                } ${getStatusColor(info.status)}`}
                onClick={() => toggleService(serviceName)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getServiceIcon(serviceName)}
                    <span className="text-sm font-medium">{serviceName}</span>
                    {getStatusIcon(info.status)}
                  </div>
                  <Badge
                    variant="secondary"
                    className={`text-xs ${getStatusColor(info.status)}`}
                  >
                    {info.status}
                  </Badge>
                </div>

                {/* Expanded details */}
                {expandedServices.has(serviceName) && (
                  <div className="mt-3 pt-3 border-t border-gray-600 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1 text-gray-400">
                        <Zap className="h-3 w-3" />
                        <span>Latency:</span>
                      </div>
                      <span className={getLatencyColor(info.latency)}>
                        {formatLatency(info.latency)}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1 text-gray-400">
                        <Clock className="h-3 w-3" />
                        <span>Last Check:</span>
                      </div>
                      <span className="text-gray-300">
                        {formatLastCheck(info.last_check)}
                      </span>
                    </div>

                    {info.error_count !== undefined && info.error_count > 0 && (
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1 text-gray-400">
                          <AlertCircle className="h-3 w-3" />
                          <span>Errors:</span>
                        </div>
                        <span className="text-red-400 font-medium">
                          {info.error_count}
                        </span>
                      </div>
                    )}

                    {/* Service actions */}
                    {onServiceAction && (
                      <div className="flex gap-2 mt-2 pt-2 border-t">
                        {(info.status === 'stopped' || info.status === 'offline') ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation();
                              onServiceAction(serviceName, 'start');
                            }}
                            className="flex-1 h-7 text-xs"
                          >
                            <Power className="h-3 w-3 mr-1" />
                            Start
                          </Button>
                        ) : (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                onServiceAction(serviceName, 'restart');
                              }}
                              className="flex-1 h-7 text-xs"
                            >
                              <RefreshCw className="h-3 w-3 mr-1" />
                              Restart
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => {
                                e.stopPropagation();
                                onServiceAction(serviceName, 'stop');
                              }}
                              className="flex-1 h-7 text-xs text-red-600 hover:text-red-700"
                            >
                              <Power className="h-3 w-3 mr-1" />
                              Stop
                            </Button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default ServiceStatusPanel;
