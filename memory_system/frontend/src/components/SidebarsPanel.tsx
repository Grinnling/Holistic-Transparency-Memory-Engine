// components/SidebarsPanel.tsx
// Sidebar conversation management panel - unified tree view
// Refactored: 2026-01-24 - Homogenized to always-tree with compress-archived toggle

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import {
  GitBranch,
  Play,
  Pause,
  Merge,
  Archive,
  ChevronDown,
  ChevronRight,
  Plus,
  Focus,
  RefreshCw,
  Trash2,
  AlertTriangle,
  Pencil,
  Check,
  X,
  Tag,
  Users,
  Search,
  ChevronLeft
} from 'lucide-react';
import { reportCaughtError } from '../utils/errorReporter';

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
  description?: string;
  display_name?: string;
  status?: string;
  tags?: string[];
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
}

const ROOTS_PER_PAGE = 25;

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
}) => {
  const [showSpawnForm, setShowSpawnForm] = useState(false);
  const [spawnReason, setSpawnReason] = useState('');
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [rootPage, setRootPage] = useState(0);

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

  // Status groupings
  const inProgressStatuses = ['active', 'paused', 'waiting', 'testing', 'reviewing', 'spawning_child', 'consolidating'];
  const completedStatuses = ['merged', 'archived', 'failed'];

  // Build a lookup map from contexts array for metadata
  const contextMap = useMemo(() => {
    const map: Record<string, SidebarContext> = {};
    contexts.forEach(ctx => { map[ctx.id] = ctx; });
    return map;
  }, [contexts]);

  // Filter tree nodes by search query (keeps ancestors of matching nodes)
  const filterTreeNode = (node: TreeNode, query: string): TreeNode | null => {
    const q = query.toLowerCase();
    const ctx = contextMap[node.id];
    const nodeMatches =
      node.id.toLowerCase().includes(q) ||
      (node.display_name || '').toLowerCase().includes(q) ||
      (node.reason || '').toLowerCase().includes(q) ||
      (node.description || '').toLowerCase().includes(q) ||
      (ctx?.display_name || '').toLowerCase().includes(q) ||
      (ctx?.reason || '').toLowerCase().includes(q) ||
      (node.tags || ctx?.tags || []).some(tag => tag.toLowerCase().includes(q));
    const filteredChildren = (node.children || [])
      .map(child => filterTreeNode(child, query))
      .filter((child): child is TreeNode => child !== null);
    if (nodeMatches || filteredChildren.length > 0) {
      return { ...node, children: filteredChildren };
    }
    return null;
  };

  // Compute filtered and paginated roots
  const displayRoots = useMemo(() => {
    if (!tree || !tree.roots) return [] as TreeNode[];
    let roots = tree.roots;
    if (searchQuery.trim()) {
      roots = roots
        .map(root => filterTreeNode(root, searchQuery.trim()))
        .filter((root): root is TreeNode => root !== null);
    }
    return roots;
  }, [tree, searchQuery, contextMap]);

  const totalRoots = displayRoots.length;
  const totalPages = Math.ceil(totalRoots / ROOTS_PER_PAGE);
  const paginatedRoots = displayRoots.slice(rootPage * ROOTS_PER_PAGE, (rootPage + 1) * ROOTS_PER_PAGE);

  // Reset page when search changes
  useEffect(() => { setRootPage(0); }, [searchQuery]);

  // Find ancestors of a node in the tree (for auto-expanding active branch)
  const findAncestors = (roots: TreeNode[], targetId: string): string[] => {
    const search = (node: TreeNode, path: string[]): string[] | null => {
      if (node.id === targetId) return path;
      if (node.children) {
        for (const child of node.children) {
          const result = search(child, [...path, node.id]);
          if (result) return result;
        }
      }
      return null;
    };
    for (const root of roots) {
      const result = search(root, []);
      if (result) return result;
    }
    return [];
  };

  // Auto-expand the branch containing the active context AND jump to correct page
  useEffect(() => {
    if (tree && activeContextId) {
      const ancestors = findAncestors(tree.roots, activeContextId);
      if (ancestors.length > 0) {
        setExpandedNodes(prev => {
          const next = new Set(prev);
          ancestors.forEach(id => next.add(id));
          // Also expand the active node itself if it has children
          next.add(activeContextId);
          return next;
        });
        // Jump to the page containing the active context's root
        const rootId = ancestors[0]; // First ancestor is the root
        const rootIndex = displayRoots.findIndex(r => r.id === rootId);
        if (rootIndex >= 0) {
          const targetPage = Math.floor(rootIndex / ROOTS_PER_PAGE);
          setRootPage(targetPage);
        }
      } else {
        // activeContextId might be a root itself (no ancestors)
        const rootIndex = displayRoots.findIndex(r => r.id === activeContextId);
        if (rootIndex >= 0) {
          const targetPage = Math.floor(rootIndex / ROOTS_PER_PAGE);
          setRootPage(targetPage);
        }
      }
    }
  }, [tree, activeContextId, displayRoots]);

  // Color scheme for status containers
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-gray-700 text-gray-200 border-gray-600';
      case 'paused':
      case 'waiting':
      case 'testing':
      case 'reviewing':
      case 'spawning_child':
      case 'consolidating':
        return 'bg-blue-900/50 text-blue-200 border-blue-800';
      case 'merged':
      case 'archived':
        return 'bg-gray-800 text-gray-400 border-gray-700';
      case 'failed':
        return 'bg-red-900/50 text-red-200 border-red-800';
      default:
        return 'bg-gray-700 text-gray-200 border-gray-600';
    }
  };

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
      reportCaughtError(error, 'SidebarsPanel', 'previewBulkArchive', {
        context: `criteria: ${JSON.stringify(bulkArchiveCriteria)}`,
        severity: 'medium'
      });
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
      reportCaughtError(error, 'SidebarsPanel', 'executeBulkArchive', {
        context: 'Bulk archive execution failed',
        severity: 'high'  // Data operation that failed after user confirmation
      });
    } finally {
      setBulkArchiveLoading(false);
    }
  };

  // Inline alias editing handlers
  const startEditing = (id: string, currentName: string) => {
    setEditingId(id);
    setEditValue(currentName);
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
      reportCaughtError(error, 'SidebarsPanel', 'saveAlias', {
        context: `contextId: ${contextId}`,
        severity: 'medium'
      });
    } finally {
      setEditingId(null);
      setEditValue('');
    }
  };

  // Tag color picker - deterministic based on tag name (baker's dozen)
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
  const startEditingTags = (id: string, currentTags: string[]) => {
    setEditingTags(id);
    setTagsValue(currentTags.join(', '));
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
      reportCaughtError(error, 'SidebarsPanel', 'saveTags', {
        context: `contextId: ${contextId}`,
        severity: 'medium'
      });
    } finally {
      setEditingTags(null);
      setTagsValue('');
    }
  };

  // Adopt another agent's alias
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
      reportCaughtError(error, 'SidebarsPanel', 'adoptAlias', {
        context: `contextId: ${contextId}, alias: ${alias}`,
        severity: 'medium'
      });
    } finally {
      setAliasContextMenu(null);
    }
  };

  // Fetch all aliases for a context
  const toggleViewAliases = async (contextId: string) => {
    if (viewingAliasesId === contextId) {
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
      reportCaughtError(error, 'SidebarsPanel', 'fetchAliases', {
        context: `contextId: ${contextId}`,
        severity: 'low'  // Just a view operation, not critical
      });
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

  // Resolve display name for a tree node (tree data + context metadata fallback)
  const getNodeDisplayName = (node: TreeNode): string => {
    const ctx = contextMap[node.id];
    return node.display_name
      || ctx?.display_name
      || (node.reason && node.reason !== 'Main conversation' ? node.reason : null)
      || (node.description && node.description !== 'Main conversation' ? node.description : null)
      || ctx?.reason
      || node.id;
  };

  // Get the atomic ID suffix (always show, dimmed)
  const getAtomicId = (nodeId: string): string => {
    // Show short form: SB-xxxx (first 4 chars after "SB-")
    if (nodeId.startsWith('SB-')) {
      return nodeId.slice(0, 7);
    }
    return nodeId.slice(0, 8);
  };

  // Unified tree node renderer
  const renderTreeNode = (node: TreeNode, depth: number = 0) => {
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const isActive = node.id === activeContextId;
    const ctx = contextMap[node.id];
    const status = node.status || ctx?.status || 'active';
    const isArchived = completedStatuses.includes(status);
    const displayName = getNodeDisplayName(node);
    const atomicId = getAtomicId(node.id);
    const tags = node.tags || ctx?.tags || [];

    // Unified item layout - archived items greyed out but same structure
    return (
      <div key={node.id} className="select-none">
        <div
          className={`py-1.5 px-2 rounded border ${
            isArchived ? 'opacity-60 ' + getStatusColor(status) : getStatusColor(status)
          } ${isActive ? 'ring-2 ring-blue-400' : ''}`}
          style={{ marginLeft: `${depth * 16}px` }}
        >
          {/* Row 1: Chevron + Icon + Name + Atomic ID + Pencil + Status */}
          <div className="flex items-center gap-1.5">
            {hasChildren ? (
              <button
                onClick={(e) => { e.stopPropagation(); toggleNode(node.id); }}
                className="p-0.5 hover:bg-gray-600 rounded text-gray-400"
              >
                {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              </button>
            ) : (
              <span className="w-4" />
            )}
            <GitBranch className="h-3 w-3 text-gray-400 flex-shrink-0" />

            {editingId === node.id ? (
              <div className="flex items-center gap-1 flex-1 min-w-0">
                <input
                  type="text"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveAlias(node.id);
                    if (e.key === 'Escape') cancelEditing();
                  }}
                  autoFocus
                  className="flex-1 px-2 py-0.5 text-sm bg-gray-900 border border-gray-600 rounded text-gray-200 min-w-0"
                />
                <button onClick={() => saveAlias(node.id)} className="p-0.5 hover:bg-gray-600 rounded">
                  <Check className="h-3 w-3 text-green-400" />
                </button>
                <button onClick={cancelEditing} className="p-0.5 hover:bg-gray-600 rounded">
                  <X className="h-3 w-3 text-red-400" />
                </button>
              </div>
            ) : (
              <>
                <span
                  className="text-sm truncate cursor-pointer hover:text-blue-300 min-w-0"
                  onDoubleClick={() => startEditing(node.id, displayName)}
                  onClick={() => onFocus(node.id)}
                  title={`Double-click to rename | ${node.id}`}
                >
                  {displayName}
                </span>
                <span className="text-xs text-gray-500 flex-shrink-0">{atomicId}</span>
                <button
                  onClick={() => startEditing(node.id, displayName)}
                  className="p-0.5 hover:bg-gray-600 rounded opacity-50 hover:opacity-100 flex-shrink-0"
                  title="Rename"
                >
                  <Pencil className="h-2.5 w-2.5" />
                </button>
              </>
            )}

            <div className="ml-auto flex-shrink-0">
              <Badge className={`text-[10px] px-1.5 py-0 ${getStatusBadgeClasses(status)}`}>
                {status}
              </Badge>
            </div>
          </div>

          {/* Row 2: Tags */}
          <div className="flex items-center gap-1 mt-1 ml-8">
            <Tag className="h-2.5 w-2.5 text-gray-500 flex-shrink-0" />
            {editingTags === node.id ? (
              <div className="flex items-center gap-1 flex-1">
                <input
                  type="text"
                  value={tagsValue}
                  onChange={(e) => setTagsValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveTags(node.id);
                    if (e.key === 'Escape') cancelEditingTags();
                  }}
                  placeholder="tag1, tag2, tag3"
                  autoFocus
                  className="flex-1 px-1 py-0.5 text-xs bg-gray-900 border border-gray-600 rounded text-gray-200"
                />
                <button onClick={() => saveTags(node.id)} className="p-0.5 hover:bg-gray-600 rounded">
                  <Check className="h-2.5 w-2.5 text-green-400" />
                </button>
                <button onClick={cancelEditingTags} className="p-0.5 hover:bg-gray-600 rounded">
                  <X className="h-2.5 w-2.5 text-red-400" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-1 flex-1 flex-wrap">
                {tags.length > 0 ? (
                  tags.map((tag: string) => (
                    <span key={tag} className={`px-1.5 py-0 rounded-full text-[10px] border ${getTagColor(tag)}`}>
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="text-gray-600 italic text-[10px]">no tags</span>
                )}
                <button
                  onClick={() => startEditingTags(node.id, tags)}
                  className="p-0.5 hover:bg-gray-600 rounded opacity-50 hover:opacity-100"
                  title="Edit tags"
                >
                  <Pencil className="h-2 w-2" />
                </button>
              </div>
            )}
          </div>

          {/* Row 3: Action buttons + aliases */}
          <div className="flex items-center gap-1 mt-1 ml-8">
            {/* Focus: any in-progress context that's not already active */}
            {!isActive && inProgressStatuses.includes(status) && (
              <Button size="sm" variant="ghost" onClick={() => onFocus(node.id)} className="h-5 text-[10px] px-1.5">
                <Focus className="h-2.5 w-2.5 mr-0.5" /> Focus
              </Button>
            )}
            {/* Pause */}
            {status === 'active' && (
              <Button size="sm" variant="ghost" onClick={() => onPause(node.id)} className="h-5 text-[10px] px-1.5">
                <Pause className="h-2.5 w-2.5 mr-0.5" /> Pause
              </Button>
            )}
            {/* Resume */}
            {(status === 'paused' || status === 'waiting') && (
              <Button size="sm" variant="ghost" onClick={() => onResume(node.id)} className="h-5 text-[10px] px-1.5">
                <Play className="h-2.5 w-2.5 mr-0.5" /> Resume
              </Button>
            )}
            {/* Merge: has parent and not already completed */}
            {(ctx?.parent_id || depth > 0) && !completedStatuses.includes(status) && (
              <Button size="sm" variant="ghost" onClick={() => onMerge(node.id)} className="h-5 text-[10px] px-1.5">
                <Merge className="h-2.5 w-2.5 mr-0.5" /> Merge
              </Button>
            )}
            {/* Archive */}
            {status !== 'archived' && (
              <Button size="sm" variant="ghost" onClick={() => onArchive(node.id)} className="h-5 text-[10px] px-1.5 text-gray-400">
                <Archive className="h-2.5 w-2.5 mr-0.5" /> Archive
              </Button>
            )}
            {/* Restore (for archived items) */}
            {status === 'archived' && (
              <Button size="sm" variant="ghost" onClick={() => onResume(node.id)} className="h-5 text-[10px] px-1.5 text-blue-400">
                <Play className="h-2.5 w-2.5 mr-0.5" /> Restore
              </Button>
            )}

            {/* Aliases browse */}
            <button
              onClick={() => toggleViewAliases(node.id)}
              className={`flex items-center gap-0.5 text-[10px] hover:text-blue-300 ml-auto ${
                viewingAliasesId === node.id ? 'text-blue-300' : 'text-gray-500'
              }`}
              title="View all agent aliases"
            >
              <Users className="h-2.5 w-2.5" />
              <span>aliases</span>
            </button>
          </div>

          {/* Expanded aliases panel */}
          {viewingAliasesId === node.id && (
            <div className="mt-1 ml-8 p-2 bg-gray-800 rounded border border-gray-700">
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
                            x: e.clientX, y: e.clientY,
                            contextId: node.id, alias: data.current
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

        {/* Children */}
        {hasChildren && isExpanded && (
          <div className="mt-0.5">
            {node.children.map(child => renderTreeNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

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
              {totalRoots || contexts.length}
            </Badge>
          </CardTitle>

          <div className="flex gap-2 flex-shrink-0">
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

        {/* Search input */}
        <div className="mt-2 relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by alias, ID, tag..."
            className="w-full pl-7 pr-7 py-1.5 text-sm bg-gray-800 border border-gray-600 rounded text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            >
              <X className="h-3 w-3" />
            </button>
          )}
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
              <label className="flex items-center gap-2 text-sm text-gray-300">
                <input
                  type="checkbox"
                  checked={bulkArchiveCriteria.emptyOnly}
                  onChange={(e) => setBulkArchiveCriteria(prev => ({ ...prev, emptyOnly: e.target.checked }))}
                  className="rounded border-gray-600 bg-gray-800"
                />
                Empty contexts only (0 exchanges)
              </label>

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

      <CardContent className="space-y-1">
        {paginatedRoots.length > 0 ? (
          paginatedRoots.map(root => renderTreeNode(root))
        ) : searchQuery ? (
          <div className="text-center text-gray-500 py-4">
            No matches for &quot;{searchQuery}&quot;
          </div>
        ) : contexts.length === 0 ? (
          <div className="text-center text-gray-500 py-8">
            No sidebars yet. Click &quot;New&quot; to spawn one.
          </div>
        ) : (
          <div className="text-center text-gray-500 py-4">
            <RefreshCw className="h-4 w-4 animate-spin inline mr-2" />
            Loading tree...
          </div>
        )}
      </CardContent>

      {/* Root pagination */}
      {totalPages > 1 && (
        <div className="px-4 py-2 border-t border-gray-700 flex items-center justify-between text-xs text-gray-400">
          <span>
            {rootPage * ROOTS_PER_PAGE + 1}-{Math.min((rootPage + 1) * ROOTS_PER_PAGE, totalRoots)} of {totalRoots} roots
          </span>
          <div className="flex gap-1">
            <button
              disabled={rootPage === 0}
              onClick={() => setRootPage(p => p - 1)}
              className="px-2 py-1 border border-gray-500 bg-gray-800 rounded hover:bg-gray-600 disabled:opacity-30"
            >
              <ChevronLeft className="h-3 w-3" />
            </button>
            <button
              disabled={rootPage >= totalPages - 1}
              onClick={() => setRootPage(p => p + 1)}
              className="px-2 py-1 border border-gray-500 bg-gray-800 rounded hover:bg-gray-600 disabled:opacity-30"
            >
              <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}
    </Card>
    </>
  );
};

export default SidebarsPanel;
