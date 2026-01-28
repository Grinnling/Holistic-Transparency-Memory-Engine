import { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

interface TerminalDisplayProps {
  wsUrl?: string;
}

// WebSocket URL from environment, with localhost fallback
const DEFAULT_TERMINAL_WS = import.meta.env.VITE_TERMINAL_WS_URL || 'ws://localhost:8765';

export function TerminalDisplay({ wsUrl = DEFAULT_TERMINAL_WS }: TerminalDisplayProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm.js terminal
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#ffffff',
        selectionBackground: '#264f78',
        black: '#000000',
        red: '#cd3131',
        green: '#0dbc79',
        yellow: '#e5e510',
        blue: '#2472c8',
        magenta: '#bc3fbc',
        cyan: '#11a8cd',
        white: '#e5e5e5',
        brightBlack: '#666666',
        brightRed: '#f14c4c',
        brightGreen: '#23d18b',
        brightYellow: '#f5f543',
        brightBlue: '#3b8eea',
        brightMagenta: '#d670d6',
        brightCyan: '#29b8db',
        brightWhite: '#e5e5e5',
      },
      cols: 120,
      rows: 40,
      scrollback: 10000,
      allowProposedApi: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;

    // Connect to WebSocket
    const connectWebSocket = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('✅ Connected to terminal broadcaster');
        setConnected(true);
        setReconnectAttempts(0);
        term.write('\r\n\x1b[32m✅ Connected to terminal broadcaster\x1b[0m\r\n');
      };

      ws.onmessage = (event) => {
        // Receive terminal output and display in xterm
        if (event.data instanceof Blob) {
          event.data.arrayBuffer().then(buffer => {
            const uint8Array = new Uint8Array(buffer);
            term.write(uint8Array);
          });
        } else if (event.data instanceof ArrayBuffer) {
          const uint8Array = new Uint8Array(event.data);
          term.write(uint8Array);
        } else {
          term.write(event.data);
        }
      };

      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setConnected(false);
      };

      ws.onclose = () => {
        console.log('🔌 Disconnected from terminal broadcaster');
        setConnected(false);
        term.write('\r\n\x1b[31m❌ Disconnected from terminal broadcaster\x1b[0m\r\n');

        // Attempt reconnection after delay
        const attempts = reconnectAttempts + 1;
        setReconnectAttempts(attempts);

        if (attempts < 10) {
          const delay = Math.min(1000 * Math.pow(2, attempts), 30000); // Exponential backoff, max 30s
          console.log(`🔄 Reconnecting in ${delay/1000}s (attempt ${attempts})...`);
          term.write(`\r\n\x1b[33m🔄 Reconnecting in ${delay/1000}s (attempt ${attempts})...\x1b[0m\r\n`);

          setTimeout(connectWebSocket, delay);
        } else {
          term.write('\r\n\x1b[31m❌ Max reconnection attempts reached. Please refresh the page.\x1b[0m\r\n');
        }
      };

      // Send terminal input to backend
      term.onData((data) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(data);
        }
      });
    };

    // Initial connection
    connectWebSocket();

    // Handle window resize
    const handleResize = () => {
      try {
        fitAddon.fit();
      } catch (e) {
        console.error('Error fitting terminal:', e);
      }
    };

    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      if (wsRef.current) {
        wsRef.current.close();
      }
      term.dispose();
    };
  }, [wsUrl]);

  return (
    <div className="h-full flex flex-col">
      {/* Connection status bar */}
      <div className="bg-gray-800 text-white px-4 py-2 flex items-center gap-3">
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
        <span className="text-sm font-medium">
          Terminal {connected ? 'Connected' : reconnectAttempts > 0 ? `Reconnecting (${reconnectAttempts}/10)...` : 'Disconnected'}
        </span>
        {!connected && reconnectAttempts < 10 && (
          <span className="text-xs text-gray-400">
            Waiting for broadcaster...
          </span>
        )}
      </div>

      {/* Terminal display */}
      <div ref={terminalRef} className="flex-1 bg-[#1e1e1e] p-2" />
    </div>
  );
}