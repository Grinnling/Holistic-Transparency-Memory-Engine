#!/usr/bin/env python3
"""Quick test to verify panel UI components work"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich import box
import time

console = Console()

# Create layout similar to our implementation
layout = Layout()

# Split into main sections
layout.split_column(
    Layout(name="status", size=3),
    Layout(name="body"),
    Layout(name="input", size=5)
)

# Split body into chat and error panel
layout["body"].split_row(
    Layout(name="chat", ratio=3),
    Layout(name="errors", ratio=1)
)

# Test data
chat_messages = [
    "[bold blue]You:[/bold blue] Testing the panel UI",
    "[bold green]AI:[/bold green] Panel UI is working correctly!",
    "[bold yellow]System:[/bold yellow] All panels rendering"
]

# Update panels
layout["status"].update(Panel("[green]● Services OK[/green] | [cyan]Model: Test[/cyan] | [yellow]🐛 Debug ON[/yellow]", style="on grey23", box=box.SIMPLE))
layout["chat"].update(Panel("\n\n".join(chat_messages), title="💬 Chat", border_style="blue"))
layout["input"].update(Panel("[bold blue]You:[/bold blue] _\n\n[dim]Type /help for commands[/dim]", title="✍️ Input", border_style="green"))
layout["errors"].update(Panel("[dim]No recent errors[/dim]", title="🚨 Errors", border_style="yellow"))

# Display for a few seconds
with Live(layout, refresh_per_second=4, screen=True) as live:
    for i in range(3):
        time.sleep(1)
        # Update with counter
        layout["input"].update(Panel(f"[bold blue]You:[/bold blue] Test {i+1}\n\n[dim]Type /help for commands[/dim]", title="✍️ Input", border_style="green"))

console.print("[green]✅ Panel UI test completed successfully![/green]")