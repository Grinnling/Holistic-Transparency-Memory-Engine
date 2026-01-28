#!/usr/bin/env python3
"""
Chat Interface Commands for Recovery System
Provides user-facing controls and status display
"""

from typing import Dict, Optional, Any, List
from datetime import datetime
from pathlib import Path
import json


class RecoveryChatInterface:
    """
    Chat interface for recovery system control and monitoring
    Integrates with rich_chat.py to provide recovery commands
    """
    
    def __init__(self, recovery_thread, recovery_monitor):
        """
        Initialize chat interface
        
        Args:
            recovery_thread: RecoveryThread instance
            recovery_monitor: RecoveryMonitor instance
        """
        self.recovery = recovery_thread
        self.monitor = recovery_monitor
        
        # Command registry
        self.commands = {
            '/recovery': self.cmd_recovery_help,
            '/recovery status': self.cmd_recovery_status,
            '/recovery force': self.cmd_force_recovery,
            '/recovery failed': self.cmd_view_failed,
            '/recovery pause': self.cmd_pause_recovery,
            '/recovery resume': self.cmd_resume_recovery,
            '/recovery retry-failed': self.cmd_retry_failed,
            '/recovery clear-old': self.cmd_clear_old_failed,
            '/recovery trends': self.cmd_view_trends
        }
    
    def process_command(self, command: str) -> Dict[str, Any]:
        """
        Process recovery command from chat
        
        Args:
            command: Full command string from user
            
        Returns:
            Response dict with display data
        """
        # Parse command
        parts = command.split()
        
        if len(parts) == 1 and parts[0] == '/recovery':
            return self.cmd_recovery_help()
        
        # Match command
        base_cmd = ' '.join(parts[:2]) if len(parts) >= 2 else command
        args = parts[2:] if len(parts) > 2 else []
        
        if base_cmd in self.commands:
            handler = self.commands[base_cmd]
            if args:
                return handler(*args)
            else:
                return handler()
        
        # Try single word after /recovery
        if len(parts) == 2:
            sub_cmd = f"/recovery {parts[1]}"
            if sub_cmd in self.commands:
                return self.commands[sub_cmd]()
        
        return {
            'type': 'error',
            'message': f"Unknown recovery command: {command}",
            'help': "Use '/recovery' to see available commands"
        }
    
    def cmd_recovery_help(self) -> Dict[str, Any]:
        """Show recovery system help"""
        return {
            'type': 'help',
            'title': '🔄 Recovery System Commands',
            'content': """
**Status & Monitoring:**
  `/recovery status`     - Full recovery status with trends
  `/recovery trends`     - View failure trends and analytics
  
**Control:**
  `/recovery force`      - Trigger immediate recovery cycle
  `/recovery pause [m]`  - Pause recovery for m minutes (default 30)
  `/recovery resume`     - Resume paused recovery
  
**Failed File Management:**
  `/recovery failed`     - View failed files by category
  `/recovery retry-failed [id]` - Retry specific failed file
  `/recovery clear-old`  - Archive failed files older than 7 days
  
**Quick Status Icons:**
  ✅ Running normally
  ⚠️ Issues detected
  🚨 Critical problems
  ⏸️ Paused
            """
        }
    
    def cmd_recovery_status(self, verbose: str = None) -> Dict[str, Any]:
        """
        Show comprehensive recovery status
        Implements both basic and detailed views as requested
        """
        # Get comprehensive status
        status = self.monitor.get_comprehensive_status(verbose='verbose' == verbose)
        recovery_status = self.recovery.get_recovery_status()
        
        # Build response
        response = {
            'type': 'status',
            'title': '📊 Recovery System Status'
        }
        
        # Basic status (always shown)
        basic_lines = [
            f"**Status:** {status['summary']}",
            f"**Uptime:** {self._format_uptime(recovery_status['performance']['uptime_seconds'])}",
            f"**Success Rate:** {recovery_status['performance']['success_rate']:.1%}"
        ]
        
        # Check for alerts
        if status['alerts']:
            basic_lines.append("\n**⚠️ Active Alerts:**")
            for alert in status['alerts']:
                basic_lines.append(f"  • {alert['message']}")
        
        # Add detailed info if verbose
        if verbose == 'verbose':
            # Performance metrics
            if 'performance' in status:
                perf = status['performance']
                basic_lines.append("\n**📈 Performance (24h):**")
                basic_lines.append(f"  • Processed: {perf['last_24h']['total_processed']}")
                basic_lines.append(f"  • Succeeded: {perf['last_24h']['total_succeeded']}")
                basic_lines.append(f"  • Failed: {perf['last_24h']['total_failed']}")
            
            # Trends
            if 'trends' in status and status['trends']:
                basic_lines.append("\n**📊 Trends:**")
                for trend in status['trends'][:5]:
                    basic_lines.append(f"  • {trend}")
            
            # System state
            if 'system' in status:
                sys = status['system']
                basic_lines.append("\n**💻 System:**")
                basic_lines.append(f"  • Memory: {sys.get('memory_usage_mb', 0)}MB ({sys.get('memory_percent', 0):.0f}%)")
                basic_lines.append(f"  • Disk Free: {sys.get('disk_free_gb', 0)}GB")
                if sys.get('episodic_latency_ms', -1) > 0:
                    basic_lines.append(f"  • Episodic Latency: {sys['episodic_latency_ms']:.0f}ms")
            
            # Recommendations
            if 'recommendations' in status and status['recommendations']:
                basic_lines.append("\n**💡 Recommendations:**")
                for rec in status['recommendations'][:3]:
                    basic_lines.append(f"  • {rec}")
        
        response['content'] = '\n'.join(basic_lines)
        
        # Add hint for verbose mode
        if verbose != 'verbose':
            response['footer'] = "Use '/recovery status verbose' for detailed metrics"
        
        return response
    
    def cmd_force_recovery(self) -> Dict[str, Any]:
        """Force immediate recovery cycle"""
        result = self.recovery.force_recovery_now()
        
        if 'error' in result:
            return {
                'type': 'error',
                'message': result['error']
            }
        
        return {
            'type': 'success',
            'title': '✅ Recovery Forced',
            'content': f"""
**Forced recovery completed:**
  • Files before: {result['pending_before']}
  • Files after: {result['pending_after']}
  • Processed: {result['processed']}
  • Duration: {result['duration_seconds']:.2f}s
            """
        }
    
    def cmd_view_failed(self, category: Optional[str] = None) -> Dict[str, Any]:
        """View failed files, optionally filtered by category"""
        summary = self.recovery.get_failed_files_summary()
        
        if summary['total_failed'] == 0:
            return {
                'type': 'info',
                'message': 'No failed files found'
            }
        
        lines = [f"**Total Failed Files:** {summary['total_failed']}\n"]
        
        # Show breakdown by error type
        lines.append("**By Error Type:**")
        for error_type, info in summary['by_error_type'].items():
            oldest = datetime.fromtimestamp(info['oldest']).strftime('%Y-%m-%d %H:%M')
            lines.append(f"  • **{error_type}**: {info['count']} files (oldest: {oldest})")
        
        # If specific category requested, show file list
        if category and category in summary['by_error_type']:
            lines.append(f"\n**Failed files in '{category}':**")
            failed_dir = self.recovery.backup_system.backup_root / 'failed' / category
            
            if failed_dir.exists():
                files = list(failed_dir.glob('*.json'))[:10]  # Show max 10
                for f in files:
                    lines.append(f"  • {f.name} ({f.stat().st_size} bytes)")
                
                if len(files) == 10:
                    lines.append("  ... and more")
        
        return {
            'type': 'info',
            'title': '❌ Failed Files',
            'content': '\n'.join(lines),
            'footer': "Use '/recovery retry-failed <file>' to retry specific files"
        }
    
    def cmd_pause_recovery(self, minutes: str = "30") -> Dict[str, Any]:
        """Pause recovery for specified minutes"""
        try:
            mins = int(minutes)
        except:
            mins = 30
        
        self.recovery.pause_recovery(mins)
        
        return {
            'type': 'success',
            'title': '⏸️ Recovery Paused',
            'content': f"Recovery paused for {mins} minutes",
            'footer': "Use '/recovery resume' to resume early"
        }
    
    def cmd_resume_recovery(self) -> Dict[str, Any]:
        """Resume paused recovery"""
        self.recovery.resume_recovery()
        
        return {
            'type': 'success',
            'title': '▶️ Recovery Resumed',
            'content': "Recovery thread resumed"
        }
    
    def cmd_retry_failed(self, file_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retry failed files
        What I actually want: Smart retry with root cause awareness
        """
        if not file_id:
            return {
                'type': 'error',
                'message': "Please specify a file ID or 'all' to retry all failed files"
            }
        
        failed_dir = self.recovery.backup_system.backup_root / 'failed'
        pending_dir = self.recovery.backup_system.backup_root / 'pending'
        
        moved_count = 0
        
        if file_id == 'all':
            # Move all failed files back to pending
            for error_dir in failed_dir.iterdir():
                if error_dir.is_dir():
                    for failed_file in error_dir.glob('*.json'):
                        new_path = pending_dir / failed_file.name
                        failed_file.rename(new_path)
                        moved_count += 1
        else:
            # Find and move specific file
            for error_dir in failed_dir.iterdir():
                if error_dir.is_dir():
                    for failed_file in error_dir.glob(f"*{file_id}*.json"):
                        new_path = pending_dir / failed_file.name
                        failed_file.rename(new_path)
                        moved_count += 1
        
        if moved_count == 0:
            return {
                'type': 'error',
                'message': f"No failed files matching '{file_id}' found"
            }
        
        return {
            'type': 'success',
            'title': '🔄 Files Queued for Retry',
            'content': f"Moved {moved_count} file(s) back to pending queue",
            'footer': "Recovery will retry them in the next cycle"
        }
    
    def cmd_clear_old_failed(self) -> Dict[str, Any]:
        """Archive old failed files"""
        failed_dir = self.recovery.backup_system.backup_root / 'failed'
        archive_dir = self.recovery.backup_system.backup_root / 'archived' / 'failed'
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        archived_count = 0
        cutoff_time = datetime.now().timestamp() - (7 * 86400)  # 7 days
        
        for error_dir in failed_dir.iterdir():
            if error_dir.is_dir():
                for failed_file in error_dir.glob('*.json'):
                    if failed_file.stat().st_mtime < cutoff_time:
                        archive_path = archive_dir / error_dir.name
                        archive_path.mkdir(exist_ok=True)
                        failed_file.rename(archive_path / failed_file.name)
                        archived_count += 1
        
        return {
            'type': 'success',
            'title': '🗄️ Old Failed Files Archived',
            'content': f"Archived {archived_count} files older than 7 days",
            'footer': f"Files moved to {archive_dir}"
        }
    
    def cmd_view_trends(self) -> Dict[str, Any]:
        """
        View failure trends and analytics
        This shows what I actually want for pattern recognition
        """
        analytics_file = self.monitor.analytics_dir / 'failure_trends.json'
        
        if not analytics_file.exists():
            return {
                'type': 'info',
                'message': 'No trend data available yet'
            }
        
        with open(analytics_file, 'r') as f:
            analytics = json.load(f)
        
        lines = ["**📊 Failure Trend Analysis**\n"]
        
        # Top failure reasons
        lines.append("**Top Failure Reasons:**")
        sorted_reasons = sorted(
            analytics['by_reason'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        
        for error_type, data in sorted_reasons[:5]:
            lines.append(f"  • **{error_type}**: {data['count']} occurrences")
            
            # Show pattern if detected
            if 'patterns' in data and data['patterns']:
                for pattern in data['patterns'][:2]:
                    lines.append(f"    → {pattern}")
        
        # Hotspots
        if analytics.get('hotspots'):
            lines.append("\n**🔥 Detected Hotspots:**")
            for hotspot in analytics['hotspots'][:3]:
                if hotspot.get('recent_spike'):
                    lines.append(f"  • ⚠️ Recent spike in {hotspot['error']} errors!")
                else:
                    lines.append(f"  • {hotspot['error']}: {hotspot['count']} total")
        
        # Recent insights
        if analytics.get('insights_log'):
            lines.append("\n**💡 Recent Insights:**")
            for entry in analytics['insights_log'][-3:]:
                timestamp = entry['timestamp'][:16]  # Trim to minute
                for insight in entry['insights']:
                    lines.append(f"  • [{timestamp}] {insight}")
        
        return {
            'type': 'analytics',
            'title': '📈 Recovery Trends',
            'content': '\n'.join(lines),
            'footer': "Trends update automatically as patterns emerge"
        }
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime seconds to human readable"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m"
        elif seconds < 86400:
            return f"{seconds/3600:.1f}h"
        else:
            return f"{seconds/86400:.1f}d"
    
    def get_status_for_dashboard(self) -> str:
        """
        Get one-line status for chat dashboard
        This is what shows in the main chat /status command
        """
        status = self.monitor.get_comprehensive_status(verbose=False)
        
        # Check for critical alerts
        critical_alerts = [a for a in status['alerts'] 
                          if a['severity'] in ['critical', 'emergency']]
        
        if critical_alerts:
            return f"🚨 Recovery: {critical_alerts[0]['message']}"
        elif status['alerts']:
            return f"⚠️ Recovery: {status['alerts'][0]['message']}"
        else:
            return f"✅ {status['summary']}"


# Example usage
if __name__ == "__main__":
    print("Recovery Chat Interface - Phase 3")
    print("Ready for integration with rich_chat.py")
    print("\nAvailable commands:")
    
    interface = RecoveryChatInterface(None, None)
    help_response = interface.cmd_recovery_help()
    print(help_response['content'])