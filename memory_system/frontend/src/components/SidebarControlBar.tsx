// components/SidebarControlBar.tsx
// Quick-access controls for sidebar management - sits above chat input
// Provides: current context indicator, Fork button, breadcrumb navigation

import React, { useState } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import {
  GitBranch,
  ChevronRight,
  ArrowLeft,
  Home
} from 'lucide-react';

// Minimal context info needed for the control bar
interface ContextInfo {
  id: string;
  reason: string | null;
  parent_id: string | null;
  status: string;
  exchange_count: number;
  inherited_count?: number;
}

// Breadcrumb path item
interface BreadcrumbItem {
  id: string;
  label: string;
  isRoot: boolean;
}

interface SidebarControlBarProps {
  activeContext: ContextInfo | null;
  breadcrumbPath: BreadcrumbItem[];  // Path from root to current context
  onFork: (reason: string) => void;
  onNavigate: (contextId: string) => void;  // Click on breadcrumb
  onBackToParent: () => void;
}

const SidebarControlBar: React.FC<SidebarControlBarProps> = ({
  activeContext,
  breadcrumbPath,
  onFork,
  onNavigate,
  onBackToParent
}) => {
  const [showForkInput, setShowForkInput] = useState(false);
  const [forkReason, setForkReason] = useState('');

  // Status badge styling - matches SidebarsPanel color scheme
  const getStatusBadgeVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (status) {
      case 'active':
        return 'default';
      case 'paused':
      case 'waiting':
      case 'testing':
      case 'reviewing':
      case 'spawning_child':
      case 'consolidating':
        return 'secondary';
      case 'merged':
      case 'archived':
        return 'outline';
      case 'failed':
        return 'destructive';
      default:
        return 'default';
    }
  };

  const handleFork = () => {
    if (!forkReason.trim()) return;
    onFork(forkReason.trim());
    setForkReason('');
    setShowForkInput(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleFork();
    } else if (e.key === 'Escape') {
      setShowForkInput(false);
      setForkReason('');
    }
  };

  // If no active context, show minimal bar
  if (!activeContext) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 border-b border-gray-700 text-sm">
        <Home className="h-4 w-4 text-gray-400" />
        <span className="text-gray-400">No active context</span>
      </div>
    );
  }

  const isInSidebar = activeContext.parent_id !== null;

  return (
    <div className="bg-gray-800 border-b border-gray-700">
      {/* Main control row */}
      <div className="flex items-center gap-2 px-3 py-2">
        {/* Breadcrumb navigation */}
        <div className="flex items-center gap-1 flex-1 min-w-0 overflow-x-auto">
          {breadcrumbPath.map((item, index) => (
            <React.Fragment key={item.id}>
              {index > 0 && (
                <ChevronRight className="h-3 w-3 text-gray-500 flex-shrink-0" />
              )}
              <button
                onClick={() => onNavigate(item.id)}
                className={`flex items-center gap-1 px-2 py-0.5 rounded text-sm truncate max-w-[150px] ${
                  item.id === activeContext.id
                    ? 'bg-gray-700 text-gray-100 font-medium'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'
                }`}
              >
                {item.isRoot && <Home className="h-3 w-3 flex-shrink-0" />}
                {!item.isRoot && <GitBranch className="h-3 w-3 flex-shrink-0" />}
                <span className="truncate">{item.label}</span>
              </button>
            </React.Fragment>
          ))}
        </div>

        {/* Status badge - shows current context state at a glance */}
        <Badge
          variant={getStatusBadgeVariant(activeContext.status)}
          className="text-xs flex-shrink-0"
          title={`${activeContext.reason || 'Context'}: ${activeContext.status}`}
        >
          {activeContext.status}
        </Badge>

        {/* Context stats - helpful for AI to know scope */}
        <div className="text-xs text-gray-500 flex-shrink-0">
          {activeContext.exchange_count} local
          {activeContext.inherited_count !== undefined && activeContext.inherited_count > 0 && (
            <span> + {activeContext.inherited_count} inherited</span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {/* Back to parent button (only in sidebars) */}
          {isInSidebar && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onBackToParent}
              className="h-7 px-2 text-xs"
              title="Back to parent context"
            >
              <ArrowLeft className="h-3 w-3 mr-1" />
              Back
            </Button>
          )}

          {/* Fork button */}
          <Button
            size="sm"
            variant={showForkInput ? "default" : "outline"}
            onClick={() => setShowForkInput(!showForkInput)}
            className="h-7 px-2 text-xs"
            title="Fork into new sidebar"
          >
            <GitBranch className="h-3 w-3 mr-1" />
            Fork
          </Button>
        </div>
      </div>

      {/* Fork input row (expandable) */}
      {showForkInput && (
        <div className="flex items-center gap-2 px-3 py-2 bg-gray-800/50 border-t border-gray-700">
          <GitBranch className="h-4 w-4 text-blue-400 flex-shrink-0" />
          <input
            type="text"
            placeholder="Why fork? (e.g., 'Investigate auth issue')"
            value={forkReason}
            onChange={(e) => setForkReason(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus
            className="flex-1 px-3 py-1.5 border border-gray-600 rounded text-sm bg-gray-900 text-gray-200 placeholder-gray-500"
          />
          <Button
            size="sm"
            onClick={handleFork}
            disabled={!forkReason.trim()}
          >
            Create
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setShowForkInput(false);
              setForkReason('');
            }}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
};

export default SidebarControlBar;
