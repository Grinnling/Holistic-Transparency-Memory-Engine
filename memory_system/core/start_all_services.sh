#!/bin/bash
# Auto-start all memory system services
# Created for Friday demo

cd /home/grinnling/Development/CODE_IMPLEMENTATION

# Start all services using service manager
python3 -c "
from service_manager import ServiceManager
from rich.console import Console

console = Console()
console.print('[bold green]🚀 Starting All Services[/bold green]')
console.print()

sm = ServiceManager(console=console)
success = sm.auto_start_services()

if success:
    console.print()
    console.print('[bold green]✅ All services started successfully![/bold green]')
    console.print()
    console.print('[cyan]Services running at:[/cyan]')
    console.print('  • API Server: http://localhost:8000')
    console.print('  • React UI: http://localhost:3000')
    console.print('  • Working Memory: http://localhost:5001')
    console.print('  • Curator: http://localhost:8004')
    console.print('  • MCP Logger: http://localhost:8001')
    console.print('  • Episodic Memory: http://localhost:8005')
else:
    console.print()
    console.print('[bold red]❌ Some services failed to start[/bold red]')
    console.print('[yellow]Check service logs in /tmp/rich_chat_services/[/yellow]')
"

# Keep terminal open to see output
read -p "Press Enter to close..."
