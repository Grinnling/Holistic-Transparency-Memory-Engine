// components/MessageBubble.tsx
// Extracted from App.tsx for cleaner separation of concerns

import React, { useState } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  confidence_score?: number;
  retrieved_context?: string[];
}

// Tunable confidence thresholds - adjust based on your use case
export interface ConfidenceThresholds {
  high: number;      // >= this = high confidence (green)
  good: number;      // >= this = good confidence (cyan)
  medium: number;    // >= this = medium confidence (yellow)
  low: number;       // >= this = low confidence (orange)
  // below low = very uncertain (red)
}

export const DEFAULT_THRESHOLDS: ConfidenceThresholds = {
  high: 0.9,
  good: 0.7,
  medium: 0.5,
  low: 0.3
};

interface MessageBubbleProps {
  message: Message;
  thresholds?: ConfidenceThresholds;
}

// Helper function to get confidence color and label
const getConfidenceInfo = (score: number | undefined, thresholds: ConfidenceThresholds) => {
  if (score === undefined || score === null) return { color: '#9ca3af', label: '', icon: '' };

  if (score >= thresholds.high) return { color: '#10b981', label: 'High confidence', icon: '●' };       // Green
  if (score >= thresholds.good) return { color: '#22d3ee', label: 'Good confidence', icon: '●' };       // Cyan
  if (score >= thresholds.medium) return { color: '#fbbf24', label: 'Medium confidence', icon: '◐' };   // Yellow
  if (score >= thresholds.low) return { color: '#fb923c', label: 'Low confidence', icon: '◔' };         // Orange
  return { color: '#ef4444', label: 'Very uncertain', icon: '○' };                                       // Red
};

const bubbleStyles = {
  user: 'bg-blue-800 text-blue-100 border-[#3e3e42]',
  system: 'bg-red-900 text-red-200 border-red-800',
  assistant: 'bg-[#2d2d30] text-gray-300 border-[#3e3e42]'
};

const labelStyles = {
  user: 'text-blue-200',
  system: 'text-red-300',
  assistant: 'text-gray-400'
};

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, thresholds = DEFAULT_THRESHOLDS }) => {
  const [showDebug, setShowDebug] = useState(false);
  const confidenceInfo = getConfidenceInfo(message.confidence_score, thresholds);

  return (
    <div className={`mb-3 p-3 rounded-lg border ${bubbleStyles[message.role]}`}>
      <div className={`text-xs font-semibold mb-1 capitalize ${labelStyles[message.role]}`}>
        {message.role}
      </div>
      <div className="whitespace-pre-wrap break-words">
        {message.content}
      </div>
      <div className="text-[11px] mt-1 opacity-60 flex justify-between items-center">
        <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
        {message.confidence_score !== undefined && (
          <span
            className="font-semibold opacity-100"
            style={{ color: confidenceInfo.color }}
            title={`Confidence: ${(message.confidence_score * 100).toFixed(0)}%`}
          >
            {confidenceInfo.icon} {confidenceInfo.label} ({(message.confidence_score * 100).toFixed(0)}%)
          </span>
        )}
      </div>

      {/* Debug panel: Retrieved memories */}
      {message.retrieved_context && message.retrieved_context.length > 0 && (
        <div className="mt-2 border-t border-[#3e3e42] pt-2">
          <button
            onClick={() => setShowDebug(!showDebug)}
            className="text-[10px] text-gray-500 bg-transparent border-none cursor-pointer px-1 py-0.5 hover:text-gray-400"
          >
            {showDebug ? '▼' : '▶'} Debug: Retrieved Memories ({message.retrieved_context.length})
          </button>
          {showDebug && (
            <div className="mt-1 text-[10px] text-gray-400 font-mono bg-[#1a1a1a] p-2 rounded max-h-[200px] overflow-y-auto">
              {message.retrieved_context.map((memory, idx) => (
                <div key={idx} className="mb-1.5 border-b border-[#2a2a2a] pb-1.5">
                  <span className="text-yellow-400">Memory {idx + 1}:</span> {memory}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MessageBubble;
