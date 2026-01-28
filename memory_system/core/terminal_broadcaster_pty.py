#!/usr/bin/env python3
"""
Terminal Broadcaster with PTY - Capture and stream rich_chat.py terminal output
Uses PTY to provide a real terminal for Rich library
"""

import asyncio
import websockets
import pty
import os
import sys
import select
import termios
import struct
import fcntl
from typing import Set


class TerminalBroadcasterPTY:
    """Capture terminal output using PTY and stream to WebSocket clients"""

    def __init__(self, command: list = None):
        self.command = command or ["python3", "rich_chat.py", "--auto-start"]
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.master_fd = None
        self.running = True

    def start_terminal_process(self):
        """Start terminal with PTY using fork/exec"""
        # Create PTY
        master_fd, slave_fd = pty.openpty()

        # Set terminal size
        winsize = struct.pack('HHHH', 40, 120, 0, 0)  # rows, cols, xpixel, ypixel
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

        pid = os.fork()

        if pid == 0:  # Child process
            # Close master, we only need slave in child
            os.close(master_fd)

            # Make slave the controlling terminal
            os.setsid()

            # Redirect stdin/stdout/stderr to slave
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)

            # Close the original slave fd
            if slave_fd > 2:
                os.close(slave_fd)

            # Set environment
            os.environ['TERM'] = 'xterm-256color'
            os.environ['COLORTERM'] = 'truecolor'

            # Change directory
            os.chdir("/home/grinnling/Development/CODE_IMPLEMENTATION")

            # Execute command
            os.execvp(self.command[0], self.command)

        else:  # Parent process
            # Close slave, we only need master in parent
            os.close(slave_fd)

            # Make master non-blocking
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            self.master_fd = master_fd
            print(f"✅ Started terminal process (PID: {pid})")
            return pid

    async def broadcast_output(self):
        """Read from PTY master and broadcast to clients"""
        print("📡 Broadcasting terminal output...")

        loop = asyncio.get_event_loop()

        while self.running:
            # Use select to wait for data with timeout
            readable, _, _ = await loop.run_in_executor(
                None, select.select, [self.master_fd], [], [], 0.1
            )

            if readable:
                try:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        # Broadcast to all connected clients
                        if self.clients:
                            await asyncio.gather(
                                *[client.send(data) for client in self.clients],
                                return_exceptions=True
                            )
                    else:
                        # EOF - terminal process ended
                        print("⚠️ Terminal process ended (EOF)")
                        break

                except OSError as e:
                    if e.errno == 5:  # EIO - process ended
                        print("⚠️ Terminal process ended (EIO)")
                        break
                    else:
                        print(f"⚠️ Error reading from PTY: {e}")
                        break

            await asyncio.sleep(0.01)

    async def handle_client_input(self, data):
        """Forward input from web client to PTY"""
        try:
            if self.master_fd:
                if isinstance(data, str):
                    os.write(self.master_fd, data.encode('utf-8'))
                else:
                    os.write(self.master_fd, data)
        except OSError as e:
            print(f"⚠️ Error writing to PTY: {e}")

    async def websocket_handler(self, websocket):
        """Handle WebSocket connections from React clients"""
        self.clients.add(websocket)
        print(f"✅ Client connected. Total clients: {len(self.clients)}")

        try:
            async for message in websocket:
                await self.handle_client_input(message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"❌ Client disconnected. Total clients: {len(self.clients)}")

    async def run(self):
        """Start the broadcaster"""
        print("🚀 Starting Terminal Broadcaster (PTY Mode)...")
        print("=" * 60)

        # Start terminal process with PTY
        pid = self.start_terminal_process()

        # Start WebSocket server
        server = await websockets.serve(
            self.websocket_handler,
            "localhost",
            8765,
            ping_interval=20,
            ping_timeout=10
        )

        print("✅ WebSocket server running on ws://localhost:8765")
        print(f"✅ Terminal process PID: {pid}")
        print("=" * 60)
        print("📺 Open React frontend to view terminal stream")
        print("🔌 Waiting for client connections...")
        print()

        # Start broadcasting
        try:
            await self.broadcast_output()
        finally:
            self.running = False

            # Cleanup
            if self.master_fd:
                try:
                    os.close(self.master_fd)
                except:
                    pass

            # Kill child process
            try:
                os.kill(pid, 15)  # SIGTERM
                print(f"🛑 Terminated terminal process (PID: {pid})")
            except:
                pass

            server.close()
            await server.wait_closed()


def main():
    """Main entry point"""
    print("🎯 Terminal Broadcaster for rich_chat.py (PTY Mode)")
    print()

    if len(sys.argv) > 1:
        command = sys.argv[1:]
    else:
        command = ["python3", "rich_chat.py", "--auto-start"]

    broadcaster = TerminalBroadcasterPTY(command=command)

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