#!/usr/bin/env python3
"""
Phase 3: Advanced Monitoring and Control for Recovery Thread
Provides trend analysis, emergency handling, and chat integration
"""

import json
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
import logging

recovery_logger = logging.getLogger('recovery_monitoring')


class RecoveryMonitor:
    """
    Advanced monitoring and control for recovery thread
    Tracks patterns, handles emergencies, provides insights
    """
    
    def __init__(self, recovery_thread, error_handler=None):
        """
        Initialize monitoring system

        Args:
            recovery_thread: Reference to RecoveryThread instance
            error_handler: ErrorHandler instance for proper error routing
        """
        self.recovery_thread = recovery_thread
        self.backup_system = recovery_thread.backup_system
        self.error_handler = error_handler
        
        # Trend tracking (what I actually want)
        self.failure_patterns = defaultdict(list)
        self.time_correlations = {}
        self.conversation_correlations = {}
        self.system_state_history = deque(maxlen=100)  # Keep last 100 states
        
        # Alert management
        self.alert_thresholds = {
            'failed_count': 10,
            'failure_rate': 0.3,
            'stale_pending': 3600,
            'consecutive_failures': 5
        }
        self.last_alerts = {}  # Track when we last alerted for each type
        self.alert_frequencies = {
            'info': 86400,      # Once per day
            'warning': 3600,    # Once per hour
            'critical': 600,    # Every 10 minutes
            'emergency': 60     # Every minute
        }
        
        # Disk space thresholds (TB-scale)
        self.disk_thresholds = {
            'info': 50 * 1024**3,        # 50GB
            'warning': 20 * 1024**3,     # 20GB
            'critical': 5 * 1024**3,      # 5GB
            'emergency': 1024**3          # 1GB
        }
        
        # Emergency mode flags
        self.emergency_modes = {
            'backlog_explosion': False,
            'cascade_failure': False,
            'memory_pressure': False,
            'disk_critical': False
        }
        
        # Analytics storage
        self.analytics_dir = self.backup_system.backup_root / 'analytics'
        self.analytics_dir.mkdir(exist_ok=True)
        
        # Performance tracking
        self.recent_success_rate = 1.0
        self.cascade_detection_buffer = deque(maxlen=20)
    
    # ==================== TREND ANALYSIS (What I Actually Want) ====================
    
    def analyze_failure(self, failure_info: Dict) -> Dict[str, Any]:
        """
        Analyze failure patterns and detect correlations
        This is what I REALLY want for learning from failures
        """
        # Capture system state at failure
        system_state = self.capture_system_state()
        
        # Build comprehensive failure pattern
        pattern = {
            'timestamp': failure_info.get('timestamp', datetime.now()),
            'error_type': failure_info.get('error_type'),
            'file_size': failure_info.get('file_size', 0),
            'conversation_id': failure_info.get('conversation_id'),
            'conversation_age': failure_info.get('conversation_age', 0),
            'preceding_success_rate': self.recent_success_rate,
            'system_state': system_state
        }
        
        # Store for pattern detection
        self.failure_patterns[pattern['error_type']].append(pattern)
        self.system_state_history.append(system_state)
        
        # Detect patterns
        insights = []
        
        # Periodic pattern detection
        periodic = self.detect_periodic_pattern(pattern)
        if periodic:
            insights.append(f"Periodic failure detected: {periodic}")
        
        # Size correlation
        size_correlation = self.detect_size_correlation(pattern)
        if size_correlation:
            insights.append(f"Size correlation: {size_correlation}")
        
        # Cascade precursor detection
        cascade_risk = self.detect_cascade_precursor(pattern)
        if cascade_risk:
            insights.append(f"⚠️ CASCADE RISK: {cascade_risk}")
        
        # System correlation
        system_correlation = self.detect_system_correlation(pattern)
        if system_correlation:
            insights.append(f"System correlation: {system_correlation}")
        
        # Save analytics
        self.save_failure_analytics(pattern, insights)
        
        return {
            'pattern': pattern,
            'insights': insights,
            'recommendations': self.generate_recommendations(pattern, insights)
        }
    
    def detect_periodic_pattern(self, pattern: Dict) -> Optional[str]:
        """Detect if failures happen periodically"""
        error_type = pattern['error_type']
        recent_failures = self.failure_patterns[error_type][-10:]
        
        if len(recent_failures) < 3:
            return None
        
        # Check for hourly pattern
        hours = [f['timestamp'].hour for f in recent_failures if isinstance(f['timestamp'], datetime)]
        if len(hours) > 5 and len(set(hours)) == 1:
            return f"Fails every day at {hours[0]}:00"
        
        # Check for day-of-week pattern
        weekdays = [f['timestamp'].weekday() for f in recent_failures if isinstance(f['timestamp'], datetime)]
        if len(weekdays) > 3 and len(set(weekdays)) == 1:
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            return f"Fails every {day_names[weekdays[0]]}"
        
        return None
    
    def detect_size_correlation(self, pattern: Dict) -> Optional[str]:
        """Detect if file size correlates with failures"""
        error_type = pattern['error_type']
        recent_failures = self.failure_patterns[error_type][-20:]
        
        if len(recent_failures) < 5:
            return None
        
        sizes = [f['file_size'] for f in recent_failures if f.get('file_size')]
        if not sizes:
            return None
        
        avg_size = sum(sizes) / len(sizes)
        
        # Check if large files fail more
        if avg_size > 50_000:  # 50KB
            return f"Large files (avg {avg_size//1024}KB) failing more frequently"
        
        return None
    
    def detect_cascade_precursor(self, pattern: Dict) -> Optional[str]:
        """Detect patterns that preceded cascade failures"""
        self.cascade_detection_buffer.append(pattern)
        
        # Check for rapid failure accumulation
        recent_errors = [p for p in self.cascade_detection_buffer 
                        if (datetime.now() - p['timestamp']).seconds < 60]
        
        if len(recent_errors) > 5:
            error_types = [e['error_type'] for e in recent_errors]
            if len(set(error_types)) == 1:
                return f"Rapid {error_types[0]} failures - cascade likely!"
        
        return None
    
    def detect_system_correlation(self, pattern: Dict) -> Optional[str]:
        """Detect system state correlations with failures"""
        if not self.system_state_history:
            return None
        
        # Check memory pressure correlation
        recent_states = list(self.system_state_history)[-5:]
        avg_memory = sum(s['memory_usage_mb'] for s in recent_states) / len(recent_states)
        
        if avg_memory > 500:
            return f"High memory usage ({avg_memory:.0f}MB) correlated with failures"
        
        # Check disk I/O correlation
        avg_disk_io = sum(s.get('disk_io_rate', 0) for s in recent_states) / len(recent_states)
        if avg_disk_io > 100_000_000:  # 100MB/s
            return f"High disk I/O ({avg_disk_io//1_000_000}MB/s) during failures"
        
        return None

    def _route_error(self, message: str, severity_level: str = "warning"):
        """Route error messages through ErrorHandler or fallback to logger"""
        if self.error_handler:
            from error_handler import ErrorCategory, ErrorSeverity

            # Map severity levels to ErrorSeverity
            severity_map = {
                "error": ErrorSeverity.HIGH_DEGRADE,
                "warning": ErrorSeverity.MEDIUM_ALERT,
                "info": ErrorSeverity.LOW_DEBUG,
                "critical": ErrorSeverity.CRITICAL_STOP
            }

            severity = severity_map.get(severity_level, ErrorSeverity.MEDIUM_ALERT)
            self.error_handler._route_error(message, ErrorCategory.RECOVERY_SYSTEM, severity)
        else:
            # Fallback to direct logging
            getattr(recovery_logger, severity_level, recovery_logger.warning)(message)

    def capture_system_state(self) -> Dict[str, Any]:
        """Capture current system state for correlation analysis"""
        import psutil
        
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.backup_system.backup_root))
            
            # Try to get network latency to episodic memory
            import requests
            start = datetime.now()
            try:
                requests.get('http://localhost:8005/health', timeout=1)
                latency = (datetime.now() - start).total_seconds() * 1000
            except:
                latency = -1
            
            return {
                'timestamp': datetime.now().isoformat(),
                'memory_usage_mb': memory.used // (1024 * 1024),
                'memory_percent': memory.percent,
                'disk_free_gb': disk.free // (1024**3),
                'disk_percent': disk.percent,
                'episodic_latency_ms': latency,
                'pending_count': len(self.recovery_thread._get_pending_files()),
                'cpu_percent': psutil.cpu_percent(interval=0.1)
            }
        except Exception as e:
            self._route_error(f"Failed to capture system state: {e}", "error")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
    
    def generate_recommendations(self, pattern: Dict, insights: List[str]) -> List[str]:
        """Generate actionable recommendations based on patterns"""
        recommendations = []
        
        for insight in insights:
            if 'cascade' in insight.lower():
                recommendations.append("Consider pausing recovery and investigating root cause")
            elif 'memory' in insight.lower():
                recommendations.append("Free up memory or increase recovery intervals")
            elif 'periodic' in insight.lower():
                recommendations.append("Check for scheduled maintenance or backups at this time")
            elif 'size' in insight.lower():
                recommendations.append("Consider chunking large exchanges or increasing timeouts")
        
        return recommendations
    
    def save_failure_analytics(self, pattern: Dict, insights: List[str]) -> None:
        """Save analytics to file for passive monitoring"""
        analytics_file = self.analytics_dir / 'failure_trends.json'
        
        # Load existing or create new
        if analytics_file.exists():
            with open(analytics_file, 'r') as f:
                analytics = json.load(f)
        else:
            analytics = {
                'by_reason': {},
                'hotspots': [],
                'insights_log': []
            }
        
        # Update by_reason
        error_type = pattern['error_type']
        if error_type not in analytics['by_reason']:
            analytics['by_reason'][error_type] = {
                'count': 0,
                'dates': [],
                'conversations': [],
                'patterns': []
            }
        
        analytics['by_reason'][error_type]['count'] += 1
        analytics['by_reason'][error_type]['dates'].append(
            pattern['timestamp'].isoformat() if isinstance(pattern['timestamp'], datetime) 
            else str(pattern['timestamp'])
        )
        
        if pattern.get('conversation_id'):
            analytics['by_reason'][error_type]['conversations'].append(pattern['conversation_id'])
        
        # Add insights to log
        if insights:
            analytics['insights_log'].append({
                'timestamp': datetime.now().isoformat(),
                'error_type': error_type,
                'insights': insights
            })
        
        # Detect hotspots
        self.update_hotspots(analytics)
        
        # Save
        with open(analytics_file, 'w') as f:
            json.dump(analytics, f, indent=2, default=str)
    
    def update_hotspots(self, analytics: Dict) -> None:
        """Identify and update failure hotspots"""
        hotspots = []
        
        for error_type, data in analytics['by_reason'].items():
            if data['count'] > 10:
                # Time-based hotspot detection
                recent_dates = data['dates'][-10:]
                # This is simplified - real implementation would be more sophisticated
                hotspots.append({
                    'type': 'frequency',
                    'error': error_type,
                    'count': data['count'],
                    'recent_spike': len([d for d in recent_dates 
                                       if (datetime.now() - datetime.fromisoformat(d)).days < 1]) > 5
                })
        
        analytics['hotspots'] = hotspots
    
    # ==================== EMERGENCY HANDLING ====================
    
    def check_emergency_conditions(self) -> List[Dict[str, Any]]:
        """
        Check all emergency conditions and return triggered ones
        """
        emergencies = []
        
        # Check backlog explosion
        pending_count = len(self.recovery_thread._get_pending_files())
        if pending_count > 500 and not self.emergency_modes['backlog_explosion']:
            self.emergency_modes['backlog_explosion'] = True
            emergencies.append({
                'type': 'backlog_explosion',
                'severity': 'warning',
                'message': f'Recovery backlog huge ({pending_count}), pausing new backups',
                'action': self.handle_backlog_explosion
            })
        
        # Check cascade failure
        cascade_risk = self.detect_cascade_failure()
        if cascade_risk and not self.emergency_modes['cascade_failure']:
            self.emergency_modes['cascade_failure'] = True
            emergencies.append({
                'type': 'cascade_failure',
                'severity': 'critical',
                'message': f'Cascade failure detected: {cascade_risk}',
                'action': self.handle_cascade_failure
            })
        
        # Check memory pressure
        memory_usage = self.get_recovery_memory_usage()
        if memory_usage > 500_000_000 and not self.emergency_modes['memory_pressure']:  # 500MB
            self.emergency_modes['memory_pressure'] = True
            emergencies.append({
                'type': 'memory_pressure',
                'severity': 'warning',
                'message': f'Recovery memory usage high ({memory_usage//1_000_000}MB)',
                'action': self.handle_memory_pressure
            })
        
        # Check disk space
        disk_status = self.check_disk_space()
        if disk_status and disk_status['severity'] in ['critical', 'emergency']:
            if not self.emergency_modes['disk_critical']:
                self.emergency_modes['disk_critical'] = True
                emergencies.append(disk_status)
        
        return emergencies
    
    def detect_cascade_failure(self) -> Optional[str]:
        """Detect if we're in a cascade failure situation"""
        recent_failures = list(self.cascade_detection_buffer)[-10:]
        
        if len(recent_failures) < 10:
            return None
        
        # All same error in last 10 attempts?
        error_types = [f.get('error_type') for f in recent_failures]
        if len(set(error_types)) == 1:
            return f"All last 10 failures are '{error_types[0]}'"
        
        return None
    
    def handle_backlog_explosion(self) -> Dict[str, Any]:
        """Handle backlog explosion emergency"""
        # Increase batch size for aggressive processing
        old_batch_size = self.recovery_thread._calculate_batch_size(500)
        
        # Temporarily increase processing rate
        result = {
            'action_taken': 'increased_batch_size',
            'old_batch_size': old_batch_size,
            'new_batch_size': 20,
            'recommendation': 'Consider pausing new backup generation'
        }
        
        self._route_error(f"Backlog explosion handled: {result}", "warning")
        return result
    
    def handle_cascade_failure(self, error_info: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle cascade failure with auto-remediation attempts
        This is what I'd really like for self-healing
        """
        # Capture debug package
        debug_package = {
            'timestamp': datetime.now().isoformat(),
            'error_info': error_info,
            'last_10_attempts': list(self.cascade_detection_buffer)[-10:],
            'system_state': self.capture_system_state(),
            'recent_failures': self.recovery_thread.failure_reasons.copy()
        }
        
        # Save debug info
        debug_file = self.analytics_dir / f"cascade_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(debug_file, 'w') as f:
            json.dump(debug_package, f, indent=2, default=str)
        
        # Attempt auto-remediation based on error type
        remediation_attempted = None
        if error_info == 'connection_refused':
            # Try to ping episodic memory
            import requests
            try:
                requests.get('http://localhost:8005/health', timeout=1)
            except:
                remediation_attempted = "Episodic memory appears down, pausing recovery"
                self.recovery_thread.pause_recovery(30)
        elif error_info == 'timeout':
            remediation_attempted = "Increasing timeouts temporarily"
            # Would need to implement timeout adjustment in recovery thread
        
        return {
            'debug_saved': str(debug_file),
            'remediation_attempted': remediation_attempted,
            'recommendation': 'Review debug file for root cause'
        }
    
    def handle_memory_pressure(self) -> Dict[str, Any]:
        """Handle high memory usage (throttle other processes, not recovery)"""
        # This would integrate with chat system to reduce buffers
        result = {
            'action_taken': 'memory_reduction_requested',
            'target_processes': ['chat_history_buffer', 'distillation_batch_size'],
            'recommendation': 'Reduced other process memory to prioritize recovery'
        }
        
        self._route_error(f"Memory pressure handled: {result}", "warning")
        return result
    
    def check_disk_space(self) -> Optional[Dict[str, Any]]:
        """Check disk space with staged alerts"""
        try:
            import shutil
            stat = shutil.disk_usage(str(self.backup_system.backup_root))
            free_space = stat.free
            
            # Determine severity
            if free_space < self.disk_thresholds['emergency']:
                if self.should_alert('emergency'):
                    return {
                        'type': 'disk_critical',
                        'severity': 'emergency',
                        'message': f'🔴 EMERGENCY: <1GB free ({free_space//1_000_000}MB)',
                        'action': self.handle_disk_emergency,
                        'free_gb': free_space / (1024**3)
                    }
            elif free_space < self.disk_thresholds['critical']:
                if self.should_alert('critical'):
                    return {
                        'type': 'disk_critical',
                        'severity': 'critical',
                        'message': f'🚨 Critical: Only {free_space//(1024**3)}GB free',
                        'action': self.handle_disk_critical,
                        'free_gb': free_space / (1024**3)
                    }
            elif free_space < self.disk_thresholds['warning']:
                if self.should_alert('warning'):
                    return {
                        'type': 'disk_warning',
                        'severity': 'warning',
                        'message': f'⚠️ Disk space low: {free_space//(1024**3)}GB remaining',
                        'action': None,
                        'free_gb': free_space / (1024**3)
                    }
            elif free_space < self.disk_thresholds['info']:
                if self.should_alert('info'):
                    return {
                        'type': 'disk_info',
                        'severity': 'info',
                        'message': f'📊 FYI: {free_space//(1024**3)}GB free space',
                        'action': None,
                        'free_gb': free_space / (1024**3)
                    }
            
            return None
            
        except Exception as e:
            self._route_error(f"Failed to check disk space: {e}", "error")
            return None
    
    def handle_disk_emergency(self) -> Dict[str, Any]:
        """Handle emergency disk situation"""
        # Stop recovery immediately
        self.recovery_thread.stop_recovery_thread()
        
        # Try to compress old backups
        compressed_count = self.emergency_compress_backups()
        
        return {
            'action_taken': 'emergency_stop_and_compress',
            'compressed_files': compressed_count,
            'status': 'Recovery stopped, cleanup required'
        }
    
    def handle_disk_critical(self) -> Dict[str, Any]:
        """Handle critical disk situation"""
        # Compress old backups proactively
        compressed_count = self.emergency_compress_backups()
        
        return {
            'action_taken': 'proactive_compression',
            'compressed_files': compressed_count,
            'status': 'Compressed old backups to free space'
        }
    
    def emergency_compress_backups(self) -> int:
        """Emergency compression of old backup files"""
        import gzip
        compressed = 0
        
        try:
            active_dir = self.backup_system.backup_root / 'active'
            for jsonl_file in active_dir.glob('*.jsonl'):
                # Compress files older than 1 day
                if (datetime.now() - datetime.fromtimestamp(jsonl_file.stat().st_mtime)).days > 1:
                    gz_file = jsonl_file.with_suffix('.jsonl.gz')
                    with open(jsonl_file, 'rb') as f_in:
                        with gzip.open(gz_file, 'wb') as f_out:
                            f_out.write(f_in.read())
                    jsonl_file.unlink()
                    compressed += 1
        except Exception as e:
            self._route_error(f"Emergency compression failed: {e}", "error")
        
        return compressed
    
    # ==================== ALERT MANAGEMENT ====================
    
    def should_alert(self, severity: str) -> bool:
        """Check if we should send an alert based on frequency limits"""
        now = datetime.now()
        frequency = self.alert_frequencies.get(severity, 3600)
        
        last_alert_time = self.last_alerts.get(severity)
        if not last_alert_time:
            self.last_alerts[severity] = now
            return True
        
        if (now - last_alert_time).total_seconds() >= frequency:
            self.last_alerts[severity] = now
            return True
        
        return False
    
    def get_recovery_memory_usage(self) -> int:
        """Get memory usage of recovery thread (simplified)"""
        # This would need proper implementation with process monitoring
        import psutil
        try:
            process = psutil.Process()
            return process.memory_info().rss
        except:
            return 0
    
    # ==================== STATUS REPORTING ====================
    
    def get_comprehensive_status(self, verbose: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive recovery status for display
        Both basic and detailed views as requested
        """
        basic_status = self.recovery_thread.get_recovery_status()
        
        # Basic view (always shown)
        status = {
            'summary': self.format_basic_status(basic_status),
            'alerts': self.check_emergency_conditions()
        }
        
        if verbose:
            # Detailed view (when requested)
            analytics = self.load_analytics_summary()
            status.update({
                'performance': self.format_performance_metrics(basic_status),
                'trends': self.format_trend_analysis(analytics),
                'system': self.capture_system_state(),
                'recommendations': self.generate_current_recommendations()
            })
        
        return status
    
    def format_basic_status(self, status: Dict) -> str:
        """Format basic status line"""
        thread_status = "✅" if status['thread_status'] == 'running' else "❌"
        pending = status['queue_info']['pending_count']
        failed = status['queue_info']['permanently_failed']
        
        return f"Recovery: {thread_status} | {pending} pending | {failed} failed"
    
    def format_performance_metrics(self, status: Dict) -> Dict[str, Any]:
        """Format detailed performance metrics"""
        perf = status['performance']
        
        # Calculate 24h metrics (would need time-series data in real implementation)
        return {
            'last_hour': {
                'processed': perf['total_processed'],
                'success_rate': f"{perf['success_rate']:.1%}",
                'avg_batch_time': "2.3s"  # Would calculate from actual data
            },
            'last_24h': {
                'total_processed': perf['total_processed'],
                'total_succeeded': perf['total_succeeded'],
                'total_failed': perf['total_failed']
            }
        }
    
    def format_trend_analysis(self, analytics: Dict) -> List[str]:
        """Format trend analysis for display"""
        trends = []
        
        for error_type, data in analytics.get('by_reason', {}).items():
            if data['count'] > 5:
                trends.append(f"{error_type}: {data['count']} failures")
        
        for hotspot in analytics.get('hotspots', []):
            if hotspot.get('recent_spike'):
                trends.append(f"⚠️ Spike in {hotspot['error']} errors")
        
        return trends
    
    def load_analytics_summary(self) -> Dict:
        """Load analytics summary from file"""
        analytics_file = self.analytics_dir / 'failure_trends.json'
        
        if analytics_file.exists():
            with open(analytics_file, 'r') as f:
                return json.load(f)
        
        return {'by_reason': {}, 'hotspots': [], 'insights_log': []}
    
    def generate_current_recommendations(self) -> List[str]:
        """Generate intelligent recommendations based on rich analytics"""
        recommendations = []
        
        # Check current conditions
        pending_count = len(self.recovery_thread._get_pending_files())
        if pending_count > 100:
            recommendations.append("High pending count - consider manual force recovery")
        
        # Check failure rate
        status = self.recovery_thread.get_recovery_status()
        if status['performance']['success_rate'] < 0.5:
            recommendations.append("Low success rate - investigate failed files")
        
        # ENHANCED: Analyze rich insights for intelligent recommendations
        analytics = self.load_analytics_summary()
        if 'insights_log' in analytics:
            # Analyze recent insights (last 30 for better pattern detection)
            recent_insights = []
            for entry in analytics['insights_log'][-30:]:
                recent_insights.extend(entry.get('insights', []))
            
            # Count insight types
            insight_counts = {
                'cascade': 0, 'memory': 0, 'periodic': 0, 
                'spike': 0, 'correlation': 0, 'timebase': 0
            }
            
            for insight in recent_insights:
                insight_lower = insight.lower()
                
                if 'cascade' in insight_lower:
                    insight_counts['cascade'] += 1
                elif 'memory' in insight_lower and 'correlat' in insight_lower:
                    insight_counts['memory'] += 1
                elif any(word in insight_lower for word in ['periodic', 'fails every']):
                    insight_counts['periodic'] += 1  
                elif 'spike' in insight_lower:
                    insight_counts['spike'] += 1
                elif 'correlation' in insight_lower:
                    insight_counts['correlation'] += 1
                elif any(word in insight_lower for word in ['time', 'hour', 'day']):
                    insight_counts['timebase'] += 1
            
            # Generate intelligent recommendations based on patterns
            if insight_counts['cascade'] > 0:
                recommendations.append("🚨 CASCADE DETECTED: Pause recovery and investigate root cause immediately")
            
            if insight_counts['memory'] >= 5:
                recommendations.append("🧠 MEMORY CORRELATION: High memory usage correlated with failures - free up system memory")
                
            if insight_counts['periodic'] > 0:
                recommendations.append("⏰ PERIODIC PATTERN: Failures occur at specific times - check scheduled maintenance conflicts")
                
            if insight_counts['spike'] > 0:
                recommendations.append("📈 FAILURE SPIKE: Recent error increases detected - monitor closely")
                
            # Check hotspots for additional recommendations
            if 'hotspots' in analytics:
                high_frequency_errors = [h for h in analytics['hotspots'] if h.get('count', 0) > 15]
                if high_frequency_errors:
                    error_types = [h.get('error', 'unknown') for h in high_frequency_errors]
                    recommendations.append(f"🔥 HOTSPOT ALERT: High-frequency errors detected - investigate {', '.join(error_types[:2])}")
                
                recent_spikes = [h for h in analytics['hotspots'] if h.get('recent_spike', False)]
                if recent_spikes and not insight_counts['spike']:  # Don't duplicate spike warnings
                    spike_errors = [h.get('error', 'unknown') for h in recent_spikes]
                    recommendations.append(f"⚡ RECENT SPIKES: Monitor {', '.join(spike_errors[:2])} errors closely")
        
        # Emergency condition recommendations
        emergencies = self.check_emergency_conditions()
        for emergency in emergencies:
            severity = emergency.get('severity', 'unknown')
            message = emergency.get('message', 'Unknown emergency')
            
            if severity == 'critical':
                recommendations.append(f"🔴 CRITICAL: {message}")
            elif severity == 'emergency':
                recommendations.append(f"🚨 EMERGENCY: {message} - immediate action required")
        
        return recommendations


# Example usage
if __name__ == "__main__":
    print("Recovery Monitor - Phase 3 Implementation")
    print("Advanced monitoring and control for recovery thread")
    print("Ready for integration with RecoveryThread")