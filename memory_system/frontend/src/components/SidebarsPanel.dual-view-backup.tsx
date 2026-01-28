// components/SidebarsPanel.tsx
// Sidebar conversation management panel - list, spawn, manage contexts

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from './ui/collapsible';
import {
  GitBranch,
  Play,
  Pause,
  Merge,
  Archive,
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  Plus,
  Focus,
  ListTree,
  List,
  RefreshCw,
  Trash2,
  AlertTriangle,
  Pencil,
  Check,
  X,
  Tag,
  Users
} from 'lucide-react';

// Match API response shape from /sidebars endpoint
export interface SidebarContext {
  id: string;
  parent_id: string | null;
  status: string;  // "active", "paused", "merged", "archived"
  reason: string | null;       // Original task_description (immutable birth record)
  display_name: string | null; // Actor-resolved alias (API returns YOUR alias based on ?actor= param)
  created_at: string | null;
  created_by?: string;
  priority?: string;
  exchange_count: number;
  inherited_count?: number;
  tags?: string[];  // Categorization labels
}

// Tree node structure from /sidebars/tree
export interface TreeNode {
  id: string;
  reason?: string;
  description?: string;  // API uses description, reason is added by augmentation
  display_name?: string;  // Actor-resolved alias from tree endpoint
  status?: string;
  children: TreeNode[];
}

// Root structure from /sidebars/tree endpoint
export interface TreeData {
  roots: TreeNode[];
}

// Per-actor alias data from /sidebars/{id}/aliases
interface ActorAliasData {
  current: string | null;
  history: {
    alias: string;
    citation_id: string;
    confidence: number;
    supersedes: string | null;
    created_at: string;
    is_current: boolean;
  }[];
}

interface PaginationInfo {
  total: number;
  filtered: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

interface SidebarsPanelProps {
  contexts: SidebarContext[];
  tree: TreeData | null;
  activeContextId: string | null;
  onSpawn: (parentId: string, reason: string) => void;
  onCreateRoot?: (description: string) => void;
  onFocus: (id: string) => void;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onMerge: (id: string) => void;
  onArchive: (id: string) => void;
  onRefresh?: () => void;
  pagination?: PaginationInfo;
  onPageChange?: (offset: number) => void;
}

const SidebarsPanel: React.FC<SidebarsPanelProps> = ({
  contexts,
  tree,
  activeContextId,
  onSpawn,
  onCreateRoot,
  onFocus,
  onPause,
  onResume,
  onMerge,
  onArchive,
  onRefresh,
  pagination,
  onPageChange
}) => {
  const [viewMode, setViewMode] = useState<'list' | 'tree'>('list');
  const [showSpawnForm, setShowSpawnForm] = useState(false);
  const [spawnReason, setSpawnReason] = useState('');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  // Bulk archive state
  const [showBulkArchive, setShowBulkArchive] = useState(false);
  const [bulkArchivePreview, setBulkArchivePreview] = useState<{ count: number; ids: string[] } | null>(null);
  const [bulkArchiveLoading, setBulkArchiveLoading] = useState(false);
  const [bulkArchiveCriteria, setBulkArchiveCriteria] = useState({
    reasonContains: '',
    exchangeCountMax: 0,
    emptyOnly: true
  });

  // Inline editing state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editingTags, setEditingTags] = useState<string | null>(null);
  const [tagsValue, setTagsValue] = useState('');

  // Browse other aliases state
  const [viewingAliasesId, setViewingAliasesId] = useState<string | null>(null);
  const [aliasData, setAliasData] = useState<Record<string, ActorAliasData> | null>(null);
  const [aliasLoading, setAliasLoading] = useState(false);

  // Right-click context menu for alias adoption
  const [aliasContextMenu, setAliasContextMenu] = useState<{
    x: number; y: number; contextId: string; alias: string;
  } | null>(null);

  // Status groupings - defined early so helper functions can use them
  // Maps to datashapes.py SidebarStatus enum (10 states)
  const inProgressStatuses = ['active', 'paused', 'waiting', 'testing', 'reviewing', 'spawning_child', 'consolidating'];
  const completedStatuses = ['merged', 'archived', 'failed'];

  // Color scheme: grey=OK, blue=uncertain/paused, red=bad
  // Full status list from datashapes.py SidebarStatus enum (10 states)
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-gray-700 text-gray-200 border-gray-600';  // Grey = working
      case 'paused':
      case 'waiting':
      case 'testing':
      case 'reviewing':
      case 'spawning_child':
      case 'consolidating':
        return 'bg-blue-900/50 text-blue-200 border-blue-800';  // Blue = uncertain/in-progress
      case 'merged':
      case 'archived':
        return 'bg-gray-800 text-gray-400 border-gray-700';  // Dim grey = done
      case 'failed':
        return 'bg-red-900/50 text-red-200 border-red-800';  // Red = bad
      default:
        return 'bg-gray-700 text-gray-200 border-gray-600';
    }
  };

  // Explicit badge colors matching container color scheme
  // Grey=normal, Blue=attention/paused, Red=bad, Dim=done
  const getStatusBadgeClasses = (status: string): string => {
    switch (status) {
      case 'active':
        return 'bg-gray-600 text-gray-200 border-gray-500';
      case 'paused':
      case 'waiting':
      case 'testing':
      case 'reviewing':
      case 'spawning_child':
      case 'consolidating':
        return 'bg-blue-700 text-blue-200 border-blue-600';
      case 'merged':
      case 'archived':
        return 'bg-gray-700 text-gray-400 border-gray-600';
      case 'failed':
        return 'bg-red-700 text-red-200 border-red-600';
      default:
        return 'bg-gray-600 text-gray-200 border-gray-500';
    }
  };

  const handleSpawn = () => {
    if (!spawnReason.trim()) return;
    // Spawn from currently active context (or first available)
    const parentId = activeContextId || contexts[0]?.id;
    if (parentId) {
      onSpawn(parentId, spawnReason.trim());
      setSpawnReason('');
      setShowSpawnForm(false);
    }
  };

  // Bulk archive handlers
  const API_BASE = 'http://localhost:8000';

  const handleBulkArchivePreview = async () => {
    setBulkArchiveLoading(true);
    try {
      const response = await fetch(`${API_BASE}/sidebars/archive-bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason_contains: bulkArchiveCriteria.reasonContains || null,
          exchange_count_max: bulkArchiveCriteria.emptyOnly ? 0 : null,
          dry_run: true
        })
      });
      if (response.ok) {
        const data = await response.json();
        setBulkArchivePreview({
          count: data.would_archive || 0,
          ids: data.matching_ids || []
        });
      }
    } catch (error) {
      console.error('Failed to preview bulk archive:', error);
    } finally {
      setBulkArchiveLoading(false);
    }
  };

  const handleBulkArchiveExecute = async () => {
    setBulkArchiveLoading(true);
    try {
      const response = await fetch(`${API_BASE}/sidebars/archive-bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason_contains: bulkArchiveCriteria.reasonContains || null,
          exchange_count_max: bulkArchiveCriteria.emptyOnly ? 0 : null,
          dry_run: false,
          archive_reason: 'bulk_cleanup'
        })
      });
      if (response.ok) {
        const data = await response.json();
        alert(`Archived ${data.archived_count} contexts`);
        setShowBulkArchive(false);
        setBulkArchivePreview(null);
        onRefresh?.();
      }
    } catch (error) {
      console.error('Failed to execute bulk archive:', error);
    } finally {
      setBulkArchiveLoading(false);
    }
  };

  // Inline alias editing handlers
  const startEditing = (ctx: SidebarContext) => {
    setEditingId(ctx.id);
    setEditValue(ctx.display_name || ctx.reason || '');
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditValue('');
  };

  const saveAlias = async (contextId: string) => {
    if (!editValue.trim()) {
      cancelEditing();
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/sidebars/${contextId}/alias`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alias: editValue.trim(),
          confidence: 1.0,
          reason: 'User renamed via UI',
          cited_by: 'human'
        })
      });
      if (response.ok) {
        onRefresh?.();
      }
    } catch (error) {
      console.error('Failed to save alias:', error);
    } finally {
      setEditingId(null);
      setEditValue('');
    }
  };

  // Tag color picker - deterministic based on tag name
  const tagColors = [
    'bg-blue-900/50 border-blue-700 text-blue-300',
    'bg-purple-900/50 border-purple-700 text-purple-300',
    'bg-green-900/50 border-green-700 text-green-300',
    'bg-amber-900/50 border-amber-700 text-amber-300',
    'bg-rose-900/50 border-rose-700 text-rose-300',
    'bg-cyan-900/50 border-cyan-700 text-cyan-300',
    'bg-orange-900/50 border-orange-700 text-orange-300',
    'bg-pink-900/50 border-pink-700 text-pink-300',
    'bg-teal-900/50 border-teal-700 text-teal-300',
    'bg-indigo-900/50 border-indigo-700 text-indigo-300',
    'bg-lime-900/50 border-lime-700 text-lime-300',
    'bg-fuchsia-900/50 border-fuchsia-700 text-fuchsia-300',
    'bg-emerald-900/50 border-emerald-700 text-emerald-300',
  ];

  const getTagColor = (tag: string): string => {
    let hash = 0;
    for (let i = 0; i < tag.length; i++) {
      hash = tag.charCodeAt(i) + ((hash << 5) - hash);
    }
    return tagColors[Math.abs(hash) % tagColors.length];
  };

  // Tags editing handlers
  const startEditingTags = (ctx: SidebarContext) => {
    setEditingTags(ctx.id);
    setTagsValue(ctx.tags?.join(', ') || '');
  };

  const cancelEditingTags = () => {
    setEditingTags(null);
    setTagsValue('');
  };

  const saveTags = async (contextId: string) => {
    const tags = tagsValue.split(',').map(t => t.trim()).filter(t => t);

    try {
      const response = await fetch(`${API_BASE}/sidebars/${contextId}/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tags,
          reason: 'User updated via UI',
          confidence: 1.0,
          updated_by: 'human'
        })
      });
      if (response.ok) {
        onRefresh?.();
      }
    } catch (error) {
      console.error('Failed to save tags:', error);
    } finally {
      setEditingTags(null);
      setTagsValue('');
    }
  };

  // Adopt another agent's alias as your own (right-click → "Use this alias")
  const adoptAlias = async (contextId: string, alias: string) => {
    try {
      const response = await fetch(`${API_BASE}/sidebars/${contextId}/alias`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alias: alias,
          confidence: 1.0,
          reason: 'Adopted from another agent',
          cited_by: 'human'
        })
      });
      if (response.ok) {
        onRefresh?.();
      }
    } catch (error) {
      console.error('Failed to adopt alias:', error);
    } finally {
      setAliasContextMenu(null);
    }
  };

  // Fetch all aliases for a context (to browse other agents' names)
  const toggleViewAliases = async (contextId: string) => {
    if (viewingAliasesId === contextId) {
      // Close if already open
      setViewingAliasesId(null);
      setAliasData(null);
      return;
    }

    setViewingAliasesId(contextId);
    setAliasLoading(true);
    try {
      const response = await fetch(`${API_BASE}/sidebars/${contextId}/aliases`);
      if (response.ok) {
        const data = await response.json();
        setAliasData(data.by_actor || {});
      }
    } catch (error) {
      console.error('Failed to fetch aliases:', error);
      setAliasData(null);
    } finally {
      setAliasLoading(false);
    }
  };

  const toggleNode = (nodeId: string) => {
    setExpandedNodes(prev => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  // Recursive tree node renderer
  const renderTreeNode = (node: TreeNode, depth: number = 0) => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const isActive = node.id === activeContextId;

    return (
      <div key={node.id} className="select-none">
        <div
          className={`flex items-center gap-2 py-1.5 px-2 rounded cursor-pointer hover:bg-gray-700 ${
            isActive ? 'bg-gray-700 border-l-2 border-blue-400' : ''
          }`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          onClick={() => onFocus(node.id)}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleNode(node.id);
              }}
              className="p-0.5 hover:bg-gray-600 rounded text-gray-400"
            >
              {isExpanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
            </button>
          ) : (
            <span className="w-4" /> // Spacer for alignment
          )}
          <GitBranch className="h-3 w-3 text-gray-400" />
          <span className="text-sm flex-1 truncate text-gray-200">
            {node.display_name
              || (node.reason && node.reason !== 'Main conversation' ? node.reason : null)
              || (node.description && node.description !== 'Main conversation' ? node.description : null)
              || node.id}
            {(node.display_name || (node.reason && node.reason !== 'Main conversation') || (node.description && node.description !== 'Main conversation')) && (
              <span className="text-xs text-gray-500 ml-1">({node.id})</span>
            )}
          </span>
          {node.status && (
            <Badge className={`text-xs ${getStatusBadgeClasses(node.status)}`}>
              {node.status}
            </Badge>
          )}
        </div>
        {hasChildren && isExpanded && (
          <div>
            {node.children.map(child => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  // List view item renderer
  const renderListItem = (ctx: SidebarContext) => {
    const isActive = ctx.id === activeContextId;

    return (
      <div
        key={ctx.id}
        className={`p-3 rounded-lg border ${getStatusColor(ctx.status)} ${
          isActive ? 'ring-2 ring-blue-400' : ''
        }`}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <GitBranch className="h-4 w-4 flex-shrink-0" />
              {editingId === ctx.id ? (
                <div className="flex items-center gap-1 flex-1">
                  <input
                    type="text"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveAlias(ctx.id);
                      if (e.key === 'Escape') cancelEditing();
                    }}
                    autoFocus
                    className="flex-1 px-2 py-0.5 text-sm bg-gray-900 border border-gray-600 rounded text-gray-200"
                  />
                  <button onClick={() => saveAlias(ctx.id)} className="p-1 hover:bg-gray-600 rounded">
                    <Check className="h-3 w-3 text-green-400" />
                  </button>
                  <button onClick={cancelEditing} className="p-1 hover:bg-gray-600 rounded">
                    <X className="h-3 w-3 text-red-400" />
                  </button>
                </div>
              ) : (
                <span
                  className="font-medium truncate cursor-pointer hover:text-blue-300"
                  onDoubleClick={() => startEditing(ctx)}
                  title="Double-click to rename"
                >
                  {ctx.display_name || ctx.reason || `Context ${ctx.id.slice(0, 8)}`}
                </span>
              )}
              {editingId !== ctx.id && (
                <button
                  onClick={() => startEditing(ctx)}
                  className="p-1 hover:bg-gray-600 rounded opacity-50 hover:opacity-100"
                  title="Rename"
                >
                  <Pencil className="h-3 w-3" />
                </button>
              )}
            </div>
            <div className="text-xs text-gray-400 mt-1 space-y-0.5">
              {/* Show both inherited and local exchange counts for context scope visibility */}
              <div>
                {ctx.exchange_count} local
                {ctx.inherited_count !== undefined && ctx.inherited_count > 0 && (
                  <span className="text-gray-500"> + {ctx.inherited_count} inherited</span>
                )}
              </div>
              {ctx.created_at && (
                <div>{new Date(ctx.created_at).toLocaleString()}</div>
              )}
              {/* Tags row */}
              <div className="flex items-center gap-1 mt-1">
                <Tag className="h-3 w-3 text-gray-500" />
                {editingTags === ctx.id ? (
                  <div className="flex items-center gap-1 flex-1">
                    <input
                      type="text"
                      value={tagsValue}
                      onChange={(e) => setTagsValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveTags(ctx.id);
                        if (e.key === 'Escape') cancelEditingTags();
                      }}
                      placeholder="tag1, tag2, tag3"
                      autoFocus
                      className="flex-1 px-1 py-0.5 text-xs bg-gray-900 border border-gray-600 rounded text-gray-200"
                    />
                    <button onClick={() => saveTags(ctx.id)} className="p-0.5 hover:bg-gray-600 rounded">
                      <Check className="h-2.5 w-2.5 text-green-400" />
                    </button>
                    <button onClick={cancelEditingTags} className="p-0.5 hover:bg-gray-600 rounded">
                      <X className="h-2.5 w-2.5 text-red-400" />
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 flex-1">
                    {ctx.tags && ctx.tags.length > 0 ? (
                      ctx.tags.map((tag: string) => (
                        <span key={tag} className={`px-1.5 py-0.5 rounded-full text-xs border ${getTagColor(tag)}`}>
                          {tag}
                        </span>
                      ))
                    ) : (
                      <span className="text-gray-500 italic">no tags</span>
                    )}
                    <button
                      onClick={() => startEditingTags(ctx)}
                      className="p-0.5 hover:bg-gray-600 rounded opacity-50 hover:opacity-100 ml-1"
                      title="Edit tags"
                    >
                      <Pencil className="h-2.5 w-2.5" />
                    </button>
                  </div>
                )}
              </div>
              {/* View other aliases button */}
              <div className="mt-1">
                <button
                  onClick={() => toggleViewAliases(ctx.id)}
                  className={`flex items-center gap-1 text-xs hover:text-blue-300 ${
                    viewingAliasesId === ctx.id ? 'text-blue-300' : 'text-gray-500'
                  }`}
                  title="View all agent aliases for this context"
                >
                  <Users className="h-3 w-3" />
                  <span>aliases</span>
                </button>
                {/* Expanded aliases panel */}
                {viewingAliasesId === ctx.id && (
                  <div className="mt-1 p-2 bg-gray-800 rounded border border-gray-700">
                    {aliasLoading ? (
                      <span className="text-xs text-gray-500">Loading...</span>
                    ) : aliasData && Object.keys(aliasData).length > 0 ? (
                      <div className="space-y-1">
                        {Object.entries(aliasData).map(([actor, data]) => (
                          <div
                            key={actor}
                            className="flex items-center gap-2 text-xs"
                            onContextMenu={(e) => {
                              if (actor !== 'human' && data.current) {
                                e.preventDefault();
                                setAliasContextMenu({
                                  x: e.clientX,
                                  y: e.clientY,
                                  contextId: ctx.id,
                                  alias: data.current
                                });
                              }
                            }}
                          >
                            <span className="text-gray-400 font-medium min-w-[60px]">{actor}:</span>
                            <span className={`text-gray-200 truncate ${actor !== 'human' && data.current ? 'cursor-[context-menu]' : ''}`}
                              title={actor !== 'human' && data.current ? 'Right-click to use this alias' : undefined}
                            >
                              {data.current || <span className="italic text-gray-500">none</span>}
                            </span>
                            {data.history.length > 1 && (
                              <span className="text-gray-600">({data.history.length} total)</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-500 italic">No aliases set by any agent</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            <Badge className={`text-xs ${getStatusBadgeClasses(ctx.status)}`}>
              {ctx.status}
            </Badge>
          </div>
        </div>

        {/* Action buttons - contextual based on status */}
        <div className="flex gap-1 mt-2 pt-2 border-t border-gray-600">
          {/* Focus: show for any in-progress context that's not already active */}
          {!isActive && inProgressStatuses.includes(ctx.status) && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onFocus(ctx.id)}
              className="h-7 text-xs"
            >
              <Focus className="h-3 w-3 mr-1" />
              Focus
            </Button>
          )}

          {/* Pause: only for active contexts (not already paused/waiting) */}
          {ctx.status === 'active' && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onPause(ctx.id)}
              className="h-7 text-xs"
            >
              <Pause className="h-3 w-3 mr-1" />
              Pause
            </Button>
          )}

          {/* Resume: for paused or waiting contexts */}
          {(ctx.status === 'paused' || ctx.status === 'waiting') && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onResume(ctx.id)}
              className="h-7 text-xs"
            >
              <Play className="h-3 w-3 mr-1" />
              Resume
            </Button>
          )}

          {/* Merge: for sidebars (has parent) that aren't already merged/archived/failed */}
          {ctx.parent_id && !completedStatuses.includes(ctx.status) && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onMerge(ctx.id)}
              className="h-7 text-xs"
            >
              <Merge className="h-3 w-3 mr-1" />
              Merge
            </Button>
          )}

          {/* Archive: for anything not already archived */}
          {ctx.status !== 'archived' && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onArchive(ctx.id)}
              className="h-7 text-xs text-gray-400"
            >
              <Archive className="h-3 w-3 mr-1" />
              Archive
            </Button>
          )}
        </div>
      </div>
    );
  };

  // Filter contexts using the status groupings defined above
  const activeContexts = contexts.filter(c => inProgressStatuses.includes(c.status));
  const completedContexts = contexts.filter(c => completedStatuses.includes(c.status));

  return (
    <>
    {/* Click-outside handler to dismiss context menu */}
    {aliasContextMenu && (
      <div
        className="fixed inset-0 z-40"
        onClick={() => setAliasContextMenu(null)}
        onContextMenu={(e) => { e.preventDefault(); setAliasContextMenu(null); }}
      />
    )}

    {/* Right-click context menu for alias adoption */}
    {aliasContextMenu && (
      <div
        className="fixed z-50 bg-gray-800 border border-gray-600 rounded shadow-lg py-1 min-w-[160px]"
        style={{ left: aliasContextMenu.x, top: aliasContextMenu.y }}
      >
        <button
          className="w-full px-3 py-1.5 text-left text-sm text-gray-200 hover:bg-gray-700 flex items-center gap-2"
          onClick={() => adoptAlias(aliasContextMenu.contextId, aliasContextMenu.alias)}
        >
          <Check className="h-3 w-3 text-green-400" />
          Use this alias
        </button>
      </div>
    )}

    <Card className="w-full bg-gray-900 border-gray-700">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="flex items-center gap-2 text-gray-100">
            <GitBranch className="h-5 w-5" />
            Sidebars
            <Badge className="ml-2 bg-gray-600 text-gray-200 border-gray-500">
              {pagination ? pagination.total : contexts.length}
            </Badge>
          </CardTitle>

          <div className="flex gap-2 flex-shrink-0">
            {/* View mode toggle */}
            <div className="flex border border-gray-500 rounded bg-gray-800">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setViewMode('list')}
                className={`h-7 px-2 ${viewMode === 'list' ? 'bg-gray-600 text-gray-100' : 'text-gray-400 hover:text-gray-200'}`}
                title="List view"
              >
                <List className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setViewMode('tree')}
                className={`h-7 px-2 ${viewMode === 'tree' ? 'bg-gray-600 text-gray-100' : 'text-gray-400 hover:text-gray-200'}`}
                title="Tree view"
              >
                <ListTree className="h-3.5 w-3.5" />
              </Button>
            </div>

            {/* Refresh button */}
            {onRefresh && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onRefresh}
                className="h-7 px-2 border border-gray-500 bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-600 rounded"
                title="Refresh sidebar list"
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
            )}

            {/* Bulk archive button */}
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowBulkArchive(!showBulkArchive)}
              className="h-7 px-2 text-red-400 hover:text-red-300"
              title="Bulk archive test data"
            >
              <Trash2 className="h-3 w-3" />
            </Button>

            {/* New sidebar button */}
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowSpawnForm(!showSpawnForm)}
              className="h-7"
            >
              <Plus className="h-3 w-3 mr-1" />
              New
            </Button>
            {onCreateRoot && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => onCreateRoot('Main conversation')}
                className="h-7 text-green-400 border-green-700 hover:bg-green-900/30"
                title="Create new root conversation"
              >
                <Plus className="h-3 w-3 mr-1" />
                Root
              </Button>
            )}
          </div>
        </div>

        {/* Spawn form */}
        {showSpawnForm && (
          <div className="mt-3 p-3 bg-gray-800 rounded-lg border border-gray-700">
            <div className="text-sm font-medium mb-2 text-gray-200">
              Spawn new sidebar from: {activeContextId ? 'current context' : 'root'}
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Reason for sidebar (e.g., 'Investigate auth issue')"
                value={spawnReason}
                onChange={(e) => setSpawnReason(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSpawn()}
                className="flex-1 px-3 py-1.5 border border-gray-600 rounded text-sm bg-gray-900 text-gray-200 placeholder-gray-500"
              />
              <Button size="sm" onClick={handleSpawn} disabled={!spawnReason.trim()}>
                <GitBranch className="h-3 w-3 mr-1" />
                Spawn
              </Button>
            </div>
          </div>
        )}

        {/* Bulk archive panel */}
        {showBulkArchive && (
          <div className="mt-3 p-3 bg-red-900/20 rounded-lg border border-red-800">
            <div className="flex items-center gap-2 text-sm font-medium mb-3 text-red-300">
              <AlertTriangle className="h-4 w-4" />
              Bulk Archive Test Data
            </div>

            <div className="space-y-3">
              {/* Filter: Empty only */}
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input
                  type="checkbox"
                  checked={bulkArchiveCriteria.emptyOnly}
                  onChange={(e) => setBulkArchiveCriteria(prev => ({ ...prev, emptyOnly: e.target.checked }))}
                  className="rounded border-gray-600 bg-gray-800"
                />
                Empty contexts only (0 exchanges)
              </label>

              {/* Filter: Reason contains */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Reason contains:</label>
                <input
                  type="text"
                  placeholder="e.g., 'test', 'broadcast'"
                  value={bulkArchiveCriteria.reasonContains}
                  onChange={(e) => setBulkArchiveCriteria(prev => ({ ...prev, reasonContains: e.target.value }))}
                  className="w-full px-2 py-1 border border-gray-600 rounded text-sm bg-gray-900 text-gray-200 placeholder-gray-500"
                />
              </div>

              {/* Preview / Execute buttons */}
              <div className="flex gap-2 pt-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleBulkArchivePreview}
                  disabled={bulkArchiveLoading}
                  className="flex-1"
                >
                  {bulkArchiveLoading ? 'Loading...' : 'Preview'}
                </Button>
                {bulkArchivePreview && bulkArchivePreview.count > 0 && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={handleBulkArchiveExecute}
                    disabled={bulkArchiveLoading}
                    className="flex-1 bg-red-600 hover:bg-red-700"
                  >
                    Archive {bulkArchivePreview.count}
                  </Button>
                )}
              </div>

              {/* Preview results */}
              {bulkArchivePreview && (
                <div className="text-sm text-gray-400 pt-2 border-t border-gray-700">
                  {bulkArchivePreview.count === 0 ? (
                    <span>No matching contexts found</span>
                  ) : (
                    <div>
                      <span className="text-red-300 font-medium">{bulkArchivePreview.count}</span> contexts will be archived
                      {bulkArchivePreview.ids.length > 0 && (
                        <div className="mt-1 text-xs text-gray-500 max-h-20 overflow-y-auto">
                          {bulkArchivePreview.ids.slice(0, 10).join(', ')}
                          {bulkArchivePreview.ids.length > 10 && '...'}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-4 max-h-96 overflow-y-auto">
        {contexts.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            No sidebars yet. Click "New" to spawn one.
          </div>
        ) : viewMode === 'tree' && tree && tree.roots ? (
          // Tree view
          <div className="space-y-1">
            {tree.roots.map(root => renderTreeNode(root))}
          </div>
        ) : (
          // List view
          <div className="space-y-4">
            {/* Active contexts */}
            {activeContexts.length > 0 && (
              <div>
                <div className="text-xs font-medium text-gray-400 uppercase mb-2">
                  Active
                </div>
                <div className="space-y-2">
                  {activeContexts.map(renderListItem)}
                </div>
              </div>
            )}

            {/* Completed contexts (collapsible) */}
            {completedContexts.length > 0 && (
              <Collapsible>
                <CollapsibleTrigger className="flex items-center gap-2 text-xs font-medium text-gray-400 uppercase hover:text-gray-300">
                  <ChevronRight className="h-3 w-3" />
                  Completed ({completedContexts.length})
                </CollapsibleTrigger>
                <CollapsibleContent className="mt-2 space-y-2">
                  {completedContexts.map(renderListItem)}
                </CollapsibleContent>
              </Collapsible>
            )}
          </div>
        )}
      </CardContent>

      {/* Pagination Controls */}
      {viewMode === 'list' && pagination && pagination.total > 0 && (
        <div className="px-4 py-3 border-t border-gray-700 flex items-center justify-between text-sm">
          <span className="text-gray-400">
            {pagination.offset + 1}-{Math.min(pagination.offset + pagination.limit, pagination.total)} of {pagination.total}
          </span>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              disabled={pagination.offset === 0}
              onClick={() => onPageChange?.(Math.max(0, pagination.offset - pagination.limit))}
              className="h-7 px-2 border border-gray-500 bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-600 rounded disabled:opacity-30"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={!pagination.hasMore}
              onClick={() => onPageChange?.(pagination.offset + pagination.limit)}
              className="h-7 px-2 border border-gray-500 bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-600 rounded disabled:opacity-30"
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </Card>
    </>
  );
};

export default SidebarsPanel;
