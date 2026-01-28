import { useState } from 'react';
import { TerminalDisplay } from './components/TerminalDisplay';

function App() {
  const [layout, setLayout] = useState<'terminal-only' | 'split' | 'multimedia-only'>('terminal-only');

  return (
    <div className="h-screen flex flex-col bg-gray-900">
      {/* Header with layout controls */}
      <header className="bg-gray-800 text-white px-4 py-3 flex items-center justify-between border-b border-gray-700">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold">Memory Intelligence Chat</h1>
          <span className="text-xs text-gray-400 bg-gray-700 px-2 py-1 rounded">
            Terminal Streaming
          </span>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setLayout('terminal-only')}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              layout === 'terminal-only' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            🖥️ Terminal Only
          </button>
          <button
            onClick={() => setLayout('split')}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              layout === 'split' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            ↔️ Split View
          </button>
          <button
            onClick={() => setLayout('multimedia-only')}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              layout === 'multimedia-only' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            📁 Multimedia Only
          </button>
        </div>
      </header>

      {/* Main content area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Terminal Display */}
        {(layout === 'terminal-only' || layout === 'split') && (
          <div className={layout === 'split' ? 'w-2/3 border-r border-gray-700' : 'w-full'}>
            <TerminalDisplay />
          </div>
        )}

        {/* Multimedia Panels */}
        {(layout === 'multimedia-only' || layout === 'split') && (
          <div className={layout === 'split' ? 'w-1/3' : 'w-full'}>
            <MultimediaPlaceholder />
          </div>
        )}
      </div>
    </div>
  );
}

function MultimediaPlaceholder() {
  return (
    <div className="h-full bg-gray-800 flex items-center justify-center">
      <div className="text-center text-gray-400">
        <div className="text-6xl mb-4">📁</div>
        <h2 className="text-xl font-semibold mb-2">Multimedia Panel</h2>
        <p className="text-sm">
          Video, documents, and file management coming soon
        </p>
      </div>
    </div>
  );
}

export default App;