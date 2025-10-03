// components/ServiceStatusPanel.tsx
// Real-time service health monitoring panel

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
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
  Archive
} from 'lucide-react';

interface ServiceInfo {
  status: 'healthy' | 'unhealthy' | 'degraded' | 'starting' | 'stopped';
  latency?: number;
  last_check: string;
  error_count?: number;
}

interface ServiceStatusPanelProps {
  services: { [serviceName: string]: ServiceInfo };
  conversationId?: string;
  onServiceAction?: (service: string, action: 'start' | 'stop' | 'restart') => void;
}

const ServiceStatusPanel: React.FC<ServiceStatusPanelProps> = ({
  services,
  conversationId,
  onServiceAction
}) => {
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Auto-refresh every 5 seconds
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        setIsRefreshing(true);
        setTimeout(() => setIsRefreshing(false), 500);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getServiceIcon = (serviceName: string) => {
    const icons: { [key: string]: React.ReactNode } = {
      'working_memory': <Brain className="h-4 w-4" />,
      'curator': <FileText className="h-4 w-4" />,
      'mcp_logger': <Database className="h-4 w-4" />,
      'episodic_memory': <Archive className="h-4 w-4" />,
    };
    return icons[serviceName] || <Activity className="h-4 w-4" />;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'degraded':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'unhealthy':
      case 'stopped':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'starting':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Activity className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'degraded':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'unhealthy':
      case 'stopped':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'starting':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getHealthScore = () => {
    const serviceList = Object.values(services);
    if (serviceList.length === 0) return 0;

    const healthyCount = serviceList.filter(s => s.status === 'healthy').length;
    return Math.round((healthyCount / serviceList.length) * 100);
  };

  const getLatencyColor = (latency?: number) => {
    if (!latency) return 'text-gray-400';
    if (latency < 100) return 'text-green-600';
    if (latency < 300) return 'text-yellow-600';
    return 'text-red-600';
  };

  const formatLatency = (latency?: number) => {
    if (!latency) return 'N/A';
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
              <span className="text-sm text-gray-600">Overall Score</span>
              <span className={`text-lg font-bold ${
                healthScore >= 75 ? 'text-green-600' :
                healthScore >= 50 ? 'text-yellow-600' : 'text-red-600'
              }`}>
                {healthScore}%
              </span>
            </div>
            <Progress value={healthScore} className="h-2" />

            {criticalServices.length > 0 && (
              <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs">
                <div className="flex items-center gap-1 text-red-700">
                  <AlertCircle className="h-3 w-3" />
                  <span className="font-medium">Critical Issues:</span>
                </div>
                {criticalServices.map(([name]) => (
                  <div key={name} className="ml-4 text-red-600">• {name}</div>
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
                  selectedService === serviceName ? 'ring-2 ring-blue-500' : ''
                } ${getStatusColor(info.status)}`}
                onClick={() => setSelectedService(
                  selectedService === serviceName ? null : serviceName
                )}
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
                {selectedService === serviceName && (
                  <div className="mt-3 pt-3 border-t border-gray-200 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1 text-gray-600">
                        <Zap className="h-3 w-3" />
                        <span>Latency:</span>
                      </div>
                      <span className={getLatencyColor(info.latency)}>
                        {formatLatency(info.latency)}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-1 text-gray-600">
                        <Clock className="h-3 w-3" />
                        <span>Last Check:</span>
                      </div>
                      <span className="text-gray-700">
                        {formatLastCheck(info.last_check)}
                      </span>
                    </div>

                    {info.error_count !== undefined && info.error_count > 0 && (
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-1 text-gray-600">
                          <AlertCircle className="h-3 w-3" />
                          <span>Errors:</span>
                        </div>
                        <span className="text-red-600 font-medium">
                          {info.error_count}
                        </span>
                      </div>
                    )}

                    {/* Service actions */}
                    {onServiceAction && (
                      <div className="flex gap-2 mt-2 pt-2 border-t">
                        {info.status === 'stopped' ? (
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