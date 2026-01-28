#!/usr/bin/env python3
"""
Terminal Broadcaster - Capture and stream rich_chat.py terminal output to web clients
Streams terminal via WebSocket for xterm.js rendering in React
"""

import asyncio
import websockets
import subprocess
import os
import signal
import sys
from typing import Set


class TerminalBroadcaster:
    """Capture terminal output and stream to WebSocket clients"""

    def __init__(self, command: list = None):
        self.command = command or ["python3", "rich_chat.py", "--auto-start"]
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.process = None
        self.running = True

    async def start_terminal(self):
        """Start the terminal process"""
        env = os.environ.copy()
        env['TERM'] = 'xterm-256color'
        env['COLORTERM'] = 'truecolor'
        env['PYTHONUNBUFFERED'] = '1'

        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            stdin=asyncio.subprocess.PIPE,
            cwd="/home/grinnling/Development/CODE_IMPLEMENTATION",
            env=env
        )

        print(f"✅ Started terminal process (PID: {self.process.pid})")
        return self.process.pid

    async def broadcast_output(self):
        """Read from terminal and broadcast to all connected clients"""
        print("📡 Broadcasting terminal output...")

        try:
            while self.running and self.process:
                # Read data from subprocess with timeout
                try:
                    data = await asyncio.wait_for(
                        self.process.stdout.read(4096),
                        timeout=0.1
                    )

                    if data:
                        # Broadcast to all connected web clients
                        if self.clients:
                            await asyncio.gather(
                                *[client.send(data) for client in self.clients],
                                return_exceptions=True
                            )
                    else:
                        # Process ended
                        print("⚠️ Terminal process ended")
                        break

                except asyncio.TimeoutError:
                    # No data available, continue
                    continue

        except Exception as e:
            print(f"⚠️ Error broadcasting: {e}")

    async def handle_client_input(self, data):
        """Forward input from web client to terminal"""
        try:
            if self.process and self.process.stdin:
                if isinstance(data, str):
                    self.process.stdin.write(data.encode('utf-8'))
                else:
                    self.process.stdin.write(data)
                await self.process.stdin.drain()
        except Exception as e:
            print(f"⚠️ Error writing to terminal: {e}")

    async def websocket_handler(self, websocket, path):
        """Handle WebSocket connections from React clients"""
        # Register new client
        self.clients.add(websocket)
        print(f"✅ Client connected. Total clients: {len(self.clients)}")

        try:
            async for message in websocket:
                # Forward input from React to terminal
                await self.handle_client_input(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # Unregister client
            self.clients.remove(websocket)
            print(f"❌ Client disconnected. Total clients: {len(self.clients)}")

    async def run(self):
        """Start the broadcaster"""
        print("🚀 Starting Terminal Broadcaster...")
        print("=" * 60)

        # Start terminal process
        pid = await self.start_terminal()

        # Start WebSocket server for React clients
        server = await websockets.serve(
            self.websocket_handler,
            "localhost",
            8765,  # WebSocket port for terminal streaming
            ping_interval=20,
            ping_timeout=10
        )

        print("✅ WebSocket server running on ws://localhost:8765")
        print(f"✅ Terminal process PID: {pid}")
        print("=" * 60)
        print("📺 Open React frontend to view terminal stream")
        print("🔌 Waiting for client connections...")
        print()

        # Start broadcasting terminal output
        try:
            await self.broadcast_output()
        finally:
            # Cleanup
            self.running = False
            if self.process:
                try:
                    self.process.terminate()
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                    print(f"🛑 Terminated terminal process (PID: {pid})")
                except asyncio.TimeoutError:
                    self.process.kill()
                    print(f"🛑 Killed terminal process (PID: {pid})")
                except Exception as e:
                    print(f"⚠️ Error terminating process: {e}")

            # Close server
            server.close()
            await server.wait_closed()


def main():
    """Main entry point"""
    print("🎯 Terminal Broadcaster for rich_chat.py")
    print()

    # Parse command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1:]
    else:
        command = ["python3", "rich_chat.py", "--auto-start"]

    broadcaster = TerminalBroadcaster(command=command)

    try:
        asyncio.run(broadcaster.run())
    except KeyboardInterrupt:
        print("\n\n🛑 Broadcaster stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()