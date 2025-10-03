# ErrorHandler Integration Guide
## How to Add ErrorHandler to rich_chat.py

---

## Files You Need to Share with Claude Code:

1. **error_handler.py** (from this chat artifact)
2. **rich_chat.py** (your existing monolithic file)
3. **This integration guide** (for reference)

---

## Step 1: Import ErrorHandler (Top of rich_chat.py)

Add these imports near the top with your other imports:

```python
from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity
```

---

## Step 2: Initialize in __init__ Method

Find the `__init__` method of `RichMemoryChat` class and add:

```python
def __init__(self, auto_start_services=False, debug_mode=False):
    # ... existing initialization code ...
    
    # Add ErrorHandler initialization
    self.error_handler = ErrorHandler(
        console=self.console,
        debug_mode=debug_mode,
        fuck_it_we_ball_mode=self.fuck_it_we_ball_mode if hasattr(self, 'fuck_it_we_ball_mode') else False
    )
    
    # ... rest of initialization ...
```

---

## Step 3: Replace Episodic Memory Error Handling

### Find These Methods and Replace Their try/except Blocks:

#### **Method 1: `archive_exchanges_to_episodic()`**

**BEFORE:**
```python
def archive_exchanges_to_episodic(self, exchanges: List[dict]):
    try:
        # ... archival code ...
    except Exception as e:
        self.episodic_archival_failures += 1
        self.add_alert_message(f"[yellow]⚠️ Episodic memory archive failed: {str(e)[:50]}...[/yellow]")
        if self.episodic_archival_failures >= 3:
            self.add_alert_message("[red]🚨 Multiple episodic memory failures![/red]")
```

**AFTER:**
```python
def archive_exchanges_to_episodic(self, exchanges: List[dict]):
    with self.error_handler.create_context_manager(
        ErrorCategory.EPISODIC_MEMORY,
        ErrorSeverity.HIGH_DEGRADE,
        operation="archive_exchanges",
        context=f"Archiving {len(exchanges)} exchanges"
    ):
        # ... archival code (no try/except needed!) ...
        
        # Track success
        self.episodic_archival_failures = 0  # Reset on success
```

#### **Method 2: `_archive_exchange_fallback()`**

**BEFORE:**
```python
def _archive_exchange_fallback(self, exchange_id, user_message, assistant_response):
    try:
        # ... fallback archival code ...
    except Exception as e:
        self.episodic_archival_failures += 1
        self.add_alert_message(f"[yellow]⚠️ Episodic memory archive failed: {str(e)[:50]}...[/yellow]")
```

**AFTER:**
```python
def _archive_exchange_fallback(self, exchange_id, user_message, assistant_response):
    with self.error_handler.create_context_manager(
        ErrorCategory.EPISODIC_MEMORY,
        ErrorSeverity.MEDIUM_ALERT,
        operation="fallback_archive",
        context=f"Fallback for exchange {exchange_id[:8]}"
    ):
        # ... fallback archival code (no try/except needed!) ...
```

#### **Method 3: Any episodic memory recall operations**

Find methods that call episodic memory for recalls and wrap them:

```python
with self.error_handler.create_context_manager(
    ErrorCategory.EPISODIC_MEMORY,
    ErrorSeverity.MEDIUM_ALERT,
    operation="recall_memory"
):
    response = requests.post(f"{self.services['episodic_memory']}/recall", ...)
```

---

## Step 4: Update Alert Display

### Find your alert rendering code and replace with:

```python
def get_current_alerts(self):
    """Get alerts from ErrorHandler instead of self.alert_messages"""
    return self.error_handler.get_alerts_for_ui(max_alerts=8)
```

### Update any UI rendering that shows alerts:

**BEFORE:**
```python
# Wherever you display alerts
for alert in self.alert_messages[-8:]:
    # ... render alert ...
```

**AFTER:**
```python
# Use ErrorHandler's alerts
for alert in self.error_handler.get_alerts_for_ui():
    # ... render alert ...
```

---

## Step 5: Add /errors Debug Command

Add this new command handler:

```python
def handle_slash_command(self, command: str) -> bool:
    """Handle slash commands - returns True if command was handled"""
    
    # ... existing commands ...
    
    elif command == "/errors":
        summary = self.error_handler.get_error_summary()
        
        self.console.print(Panel(
            f"[bold]Error Statistics[/bold]\n\n"
            f"Total Errors: {summary['total_errors']}\n"
            f"Last Hour: {summary['last_hour']}\n"
            f"Suppressed: {summary['suppressed_total']}\n\n"
            f"[bold]By Category:[/bold]\n" +
            "\n".join(f"  • {cat}: {count}" for cat, count in summary['by_category'].items()) +
            "\n\n[dim]Use /clear_errors to reset statistics[/dim]",
            title="🔍 Error Dashboard",
            border_style="cyan"
        ))
        return True
    
    elif command == "/clear_errors":
        self.error_handler.reset_stats()
        self.console.print("[green]✓ Error statistics cleared[/green]")
        return True
    
    # ... rest of commands ...
```

---

## Step 6: Test the Integration

### Testing Checklist:

1. **Start rich_chat.py**
   - Should initialize without errors
   - No errors about missing ErrorHandler

2. **Trigger episodic memory errors**
   - Stop episodic memory service: `systemctl stop episodic_memory`
   - Try to chat - should see ONE alert, not flooding
   - Wait 30 seconds, try again - should see another alert

3. **Check alert suppression**
   - Keep chatting with episodic down
   - Should only see occasional alerts, not every message
   - Check `/errors` command to see suppression count

4. **Verify debug mode**
   - Start with `--debug` flag
   - Should see suppression messages in console
   - Should see LOW_DEBUG severity errors

5. **Test FIWB mode**
   - Use `/fiwb` command to toggle
   - Should see full tracebacks for errors
   - Should see TRACE_FIWB severity errors

---

## Expected Behavior Changes:

### Before ErrorHandler:
```
⚠️ Episodic memory archive failed: Connection refused
⚠️ Episodic memory archive failed: Connection refused  
⚠️ Episodic memory archive failed: Connection refused
⚠️ Episodic memory archive failed: Connection refused
🚨 Multiple episodic memory failures! Long-term memories not being saved.
⚠️ Episodic memory archive failed: Connection refused
⚠️ Episodic memory archive failed: Connection refused
[Chat area completely flooded]
```

### After ErrorHandler:
```
⚠️ episodic: ConnectionError (archive_exchanges) - Connection refused...
[30 seconds of clean chat]
⚠️ episodic: ConnectionError (archive_exchanges) - Connection refused...
[More clean chat - alerts properly spaced]
```

---

## Common Issues & Solutions:

### Issue: ImportError for ErrorHandler
**Solution:** Make sure `error_handler.py` is in the same directory as `rich_chat.py`

### Issue: Still seeing alert floods
**Solution:** Make sure you replaced ALL episodic memory try/except blocks with context managers

### Issue: Not seeing any error alerts
**Solution:** Check that `self.error_handler.get_alerts_for_ui()` is being called in your UI rendering

### Issue: /errors command not working
**Solution:** Make sure you added the command handler to your slash command processing

---

## Files to Share with Claude Code:

1. **error_handler.py** - The complete implementation (from chat artifact)
2. **rich_chat.py** - Your existing file that needs integration
3. **This guide** - For reference on what to change

**Tell Claude Code:** "I need to integrate the ErrorHandler class into rich_chat.py following the steps in this integration guide. Please help me make these changes."

---

## Success Metrics:

✅ No more alert flooding from episodic memory
✅ Clean chat interface with properly spaced alerts
✅ `/errors` command shows error statistics
✅ Alert suppression working (check suppressed count)
✅ Debug mode shows suppression messages
✅ FIWB mode shows full tracebacks
