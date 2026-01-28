// components/ErrorPanel.tsx
// This gives Claude what he needs to be more effective!

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible';
import { ChevronDown, ChevronRight, Copy, X, AlertTriangle, Info, AlertCircle, Bug, ChevronsUpDown } from 'lucide-react';

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

interface ErrorPanelProps {
  errors: ErrorEvent[];
  onAcknowledge: (errorId: string) => void;
  onClear: () => void;
  onReportFix: (errorId: string, worked: boolean) => void;
}

const ErrorPanel: React.FC<ErrorPanelProps> = ({
  errors,
  onAcknowledge,
  onClear,
  onReportFix
}) => {
  console.log('DEBUG: ErrorPanel rendering with', errors.length, 'errors');
  const [filter, setFilter] = useState<'all' | 'critical' | 'warning' | 'normal' | 'debug'>('all');
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');

  // Group similar errors
  const groupedErrors = React.useMemo(() => {
    const groups: { [key: string]: ErrorEvent[] } = {};
    
    errors.forEach(error => {
      // Simple grouping by error message prefix
      const key = error.error.split(':')[0] || error.error.substring(0, 50);
      if (!groups[key]) groups[key] = [];
      groups[key].push(error);
    });
    
    return groups;
  }, [errors]);

  // Filter errors
  const filteredGroups = React.useMemo(() => {
    const filtered: { [key: string]: ErrorEvent[] } = {};
    
    Object.entries(groupedErrors).forEach(([key, errorList]) => {
      const filteredList = errorList.filter(error => {
        // Filter by severity
        if (filter !== 'all' && error.severity !== filter) return false;
        
        // Filter by search term
        if (searchTerm && !error.error.toLowerCase().includes(searchTerm.toLowerCase())) {
          return false;
        }
        
        return true;
      });
      
      if (filteredList.length > 0) {
        filtered[key] = filteredList;
      }
    });
    
    return filtered;
  }, [groupedErrors, filter, searchTerm]);

  // Color scheme: grey=ok/info, blue=warning/suspicious, red=critical/bad
  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return <AlertCircle className="h-4 w-4 text-red-400" />;   // Red = bad
      case 'warning': return <AlertTriangle className="h-4 w-4 text-blue-400" />; // Blue = suspicious
      case 'debug': return <Bug className="h-4 w-4 text-gray-400" />;             // Grey = info
      default: return <Info className="h-4 w-4 text-gray-400" />;                 // Grey = info
    }
  };

  // Dark theme colors: grey=ok/info, blue=warning/suspicious, red=critical/bad
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-900/50 text-red-200 border-red-800';        // Red = bad
      case 'warning': return 'bg-blue-900/50 text-blue-200 border-blue-800';      // Blue = suspicious
      case 'debug': return 'bg-gray-800 text-gray-300 border-gray-700';           // Grey = info
      default: return 'bg-gray-700 text-gray-200 border-gray-600';                // Grey = info
    }
  };

  const copyError = (error: ErrorEvent) => {
    const errorText = `Error: ${error.error}
Time: ${new Date(error.timestamp).toLocaleString()}
Operation: ${error.operation_context || 'Unknown'}
Service: ${error.service || 'Unknown'}
Severity: ${error.severity}
Fixes Attempted: ${error.attempted_fixes.join(', ') || 'None'}
Fix Success: ${error.fix_success ?? 'Unknown'}`;

    navigator.clipboard.writeText(errorText).then(() => {
      console.log('Error copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy: ', err);
    });
  };

  const toggleGroup = (groupKey: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedGroups(new Set(Object.keys(filteredGroups)));
  };

  const collapseAll = () => {
    setExpandedGroups(new Set());
  };

  const expandCriticals = () => {
    const criticalKeys = Object.entries(filteredGroups)
      .filter(([_, errors]) => errors.some(e => e.severity === 'critical'))
      .map(([key]) => key);
    setExpandedGroups(prev => new Set([...prev, ...criticalKeys]));
  };

  const criticalCount = errors.filter(e => e.severity === 'critical').length;
  const warningCount = errors.filter(e => e.severity === 'warning').length;

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            🚨 Error Intelligence Panel
            {criticalCount > 0 && (
              <Badge variant="destructive" className="animate-pulse">
                {criticalCount} Critical
              </Badge>
            )}
            {warningCount > 0 && (
              <Badge variant="secondary">
                {warningCount} Warning
              </Badge>
            )}
          </CardTitle>
          
          <div className="flex gap-2">
            {criticalCount > 0 && (
              <Button variant="outline" size="sm" onClick={expandCriticals} title="Expand critical errors">
                <AlertCircle className="h-4 w-4 mr-1" />
                Expand Criticals
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={expandAll} title="Expand all">
              <ChevronsUpDown className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={collapseAll} title="Collapse all">
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={onClear}>
              Clear All
            </Button>
          </div>
        </div>
        
        {/* Filters */}
        <div className="space-y-2">
          <div className="flex gap-1 w-full">
            {['all', 'critical', 'warning', 'normal', 'debug'].map((severityFilter) => (
              <Button
                key={severityFilter}
                variant={filter === severityFilter ? "default" : "outline"}
                size="sm"
                className="flex-1 text-xs"
                onClick={() => setFilter(severityFilter as any)}
              >
                {severityFilter}
              </Button>
            ))}
          </div>

          <input
            type="text"
            placeholder="Search errors..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-3 py-1.5 border border-gray-600 rounded text-sm bg-gray-800 text-gray-200 placeholder-gray-500"
          />
        </div>
      </CardHeader>
      
      <CardContent className="space-y-2 max-h-96 overflow-y-auto">
        {Object.keys(filteredGroups).length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            {errors.length === 0 ? "No errors detected! 🎉" : "No errors match your filters"}
          </div>
        ) : (
          Object.entries(filteredGroups).map(([groupKey, errorList]) => {
            const isExpanded = expandedGroups.has(groupKey);
            return (
            <div key={groupKey} className="border rounded-lg">
              <Collapsible open={isExpanded} onOpenChange={() => toggleGroup(groupKey)}>
                <CollapsibleTrigger asChild>
                  <div className="flex items-center gap-2 p-3 hover:bg-gray-50 cursor-pointer">
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 transition-transform" />
                    ) : (
                      <ChevronRight className="h-4 w-4 transition-transform" />
                    )}
                    {getSeverityIcon(errorList[0].severity)}
                    <span className="flex-1 text-sm font-medium">{groupKey}</span>
                    <Badge variant="secondary">{errorList.length}</Badge>
                  </div>
                </CollapsibleTrigger>
                
                <CollapsibleContent className="border-t">
                  {errorList.map((error) => (
                    <div key={error.id} className={`p-3 border-l-4 ${getSeverityColor(error.severity)}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 space-y-1">
                          <div className="text-sm font-medium">{error.error}</div>
                          
                          {error.operation_context && (
                            <div className="text-xs text-gray-600">
                              <strong>Operation:</strong> {error.operation_context}
                            </div>
                          )}
                          
                          <div className="flex items-center gap-2 text-xs text-gray-500">
                            <span>{new Date(error.timestamp).toLocaleString()}</span>
                            {error.service && <span>• {error.service}</span>}
                          </div>
                          
                          {/* Fix tracking - This is what Claude needs! */}
                          {error.attempted_fixes.length > 0 && (
                            <div className="text-xs space-y-1">
                              <div className="font-medium text-gray-700">Attempted fixes:</div>
                              {error.attempted_fixes.map((fix, i) => (
                                <div key={i} className="ml-2 text-gray-600">• {fix}</div>
                              ))}
                              
                              {error.fix_success === null && (
                                <div className="flex gap-2 mt-2">
                                  <span className="text-xs text-gray-600">Did the fix work?</span>
                                  <Button 
                                    size="sm" 
                                    variant="outline" 
                                    onClick={() => onReportFix(error.id, true)}
                                    className="h-6 px-2 text-xs"
                                  >
                                    ✅ Yes
                                  </Button>
                                  <Button 
                                    size="sm" 
                                    variant="outline" 
                                    onClick={() => onReportFix(error.id, false)}
                                    className="h-6 px-2 text-xs"
                                  >
                                    ❌ No
                                  </Button>
                                </div>
                              )}
                              
                              {error.fix_success !== null && (
                                <div className={`text-xs ${error.fix_success ? 'text-green-600' : 'text-red-600'}`}>
                                  Fix {error.fix_success ? 'worked! ✅' : 'failed ❌'}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                        
                        <div className="flex gap-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => copyError(error)}
                            className="h-8 w-8 p-0"
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          
                          {!error.acknowledged && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => onAcknowledge(error.id)}
                              className="h-8 w-8 p-0"
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </CollapsibleContent>
              </Collapsible>
            </div>
            );
          })
        )}
      </CardContent>
    </Card>
  );
};

export default ErrorPanel;