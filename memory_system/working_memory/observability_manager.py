#!/usr/bin/env python3
"""
Observability Manager for Working Memory
Provides metrics collection, performance monitoring, and operational insights
"""

import time
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
import json
import threading

logger = logging.getLogger(__name__)

@dataclass
class OperationMetric:
    """Tracks metrics for a single operation type"""
    name: str
    count: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None
    last_timestamp: Optional[datetime] = None
    
    def record_operation(self, duration: float, success: bool = True, error: Optional[str] = None):
        """Record a single operation"""
        self.count += 1
        self.total_duration += duration
        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)
        self.last_timestamp = datetime.now(timezone.utc)
        
        if not success:
            self.error_count += 1
            self.last_error = error
    
    def get_stats(self) -> Dict:
        """Get operation statistics"""
        avg_duration = self.total_duration / self.count if self.count > 0 else 0
        
        return {
            'operation': self.name,
            'count': self.count,
            'avg_duration_ms': round(avg_duration * 1000, 2),
            'min_duration_ms': round(self.min_duration * 1000, 2) if self.count > 0 else 0,
            'max_duration_ms': round(self.max_duration * 1000, 2),
            'total_duration_s': round(self.total_duration, 2),
            'error_count': self.error_count,
            'error_rate': round(self.error_count / self.count * 100, 2) if self.count > 0 else 0,
            'last_error': self.last_error,
            'last_timestamp': self.last_timestamp.isoformat() if self.last_timestamp else None
        }

@dataclass
class BufferMetrics:
    """Tracks buffer-specific metrics"""
    total_adds: int = 0
    total_recalls: int = 0
    total_searches: int = 0
    total_evictions: int = 0
    total_archives: int = 0
    buffer_full_events: int = 0
    max_buffer_utilization: float = 0.0
    current_buffer_size: int = 0
    buffer_size_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def record_buffer_state(self, current_size: int, max_size: int):
        """Record buffer state snapshot"""
        utilization = current_size / max_size if max_size > 0 else 0
        self.current_buffer_size = current_size
        self.max_buffer_utilization = max(self.max_buffer_utilization, utilization)
        self.buffer_size_history.append({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'size': current_size,
            'utilization': round(utilization * 100, 2)
        })
        
        if utilization >= 1.0:
            self.buffer_full_events += 1

class MemoryHealthMonitor:
    """Monitors memory system health indicators"""
    
    def __init__(self):
        self.health_checks = {
            'buffer_available': True,
            'encryption_available': True,
            'lifecycle_available': True,
            'retrieval_available': True,
            'episodic_service_reachable': False
        }
        
        self.performance_thresholds = {
            'slow_operation_ms': float(os.getenv('MEMORY_SLOW_OPERATION_MS', '500')),
            'high_error_rate_percent': float(os.getenv('MEMORY_HIGH_ERROR_RATE', '5')),
            'buffer_warning_utilization': float(os.getenv('MEMORY_BUFFER_WARNING_UTIL', '0.8'))
        }
        
        self.alerts = deque(maxlen=50)  # Keep last 50 alerts
    
    def check_health(self, metrics: Dict[str, Any]) -> Dict:
        """Perform health check and return status"""
        issues = []
        warnings = []
        
        # Check component availability
        for component, available in self.health_checks.items():
            if not available:
                issues.append(f"{component} is not available")
        
        # Check performance metrics
        for op_name, op_metric in metrics.get('operations', {}).items():
            if isinstance(op_metric, dict):
                # Check for slow operations
                avg_duration = op_metric.get('avg_duration_ms', 0)
                if avg_duration > self.performance_thresholds['slow_operation_ms']:
                    warnings.append(f"{op_name} is slow: {avg_duration}ms average")
                
                # Check error rates
                error_rate = op_metric.get('error_rate', 0)
                if error_rate > self.performance_thresholds['high_error_rate_percent']:
                    issues.append(f"{op_name} has high error rate: {error_rate}%")
        
        # Check buffer utilization
        buffer_metrics = metrics.get('buffer_metrics', {})
        current_size = buffer_metrics.get('current_size', 0)
        max_size = buffer_metrics.get('max_size', 1)
        utilization = current_size / max_size
        
        if utilization >= self.performance_thresholds['buffer_warning_utilization']:
            warnings.append(f"Buffer utilization high: {utilization * 100:.1f}%")
        
        # Determine overall health status
        if issues:
            status = 'unhealthy'
        elif warnings:
            status = 'degraded'
        else:
            status = 'healthy'
        
        health_report = {
            'status': status,
            'issues': issues,
            'warnings': warnings,
            'checked_at': datetime.now(timezone.utc).isoformat(),
            'component_status': self.health_checks.copy()
        }
        
        # Record alerts for issues
        if issues or warnings:
            self.alerts.append({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'level': 'error' if issues else 'warning',
                'messages': issues + warnings
            })
        
        return health_report
    
    def update_component_status(self, component: str, available: bool):
        """Update component availability status"""
        if component in self.health_checks:
            self.health_checks[component] = available
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Get recent health alerts"""
        return list(self.alerts)[-limit:]

class ObservabilityManager:
    """Main observability manager for working memory"""
    
    def __init__(self):
        # Operation metrics tracking
        self.operation_metrics = {}
        self.metrics_lock = threading.Lock()
        
        # Buffer-specific metrics
        self.buffer_metrics = BufferMetrics()
        
        # Memory health monitor
        self.health_monitor = MemoryHealthMonitor()
        
        # Time-series data for trends
        self.metrics_history = deque(maxlen=1000)  # Keep last 1000 snapshots
        
        # Performance profiling
        self.slow_operations = deque(maxlen=50)  # Track last 50 slow operations
        
        # Custom metrics
        self.custom_metrics = defaultdict(lambda: defaultdict(float))
        
        # Memory integrity metrics
        self.memory_integrity_metrics = {
            'validation_requests': 0,
            'validation_failures': 0,
            'contradictions_found': 0,
            'context_violations': 0,
            'cross_conversation_bleeds': 0,
            'uncertainty_flags': 0,
            'retrieval_confidence_total': 0.0,
            'retrieval_confidence_count': 0
        }
        
        # Start time for uptime calculation
        self.start_time = datetime.now(timezone.utc)
        
        logger.info("Observability manager initialized")
    
    def record_operation(self, operation_name: str, duration: float, 
                        success: bool = True, error: Optional[str] = None,
                        metadata: Dict = None):
        """Record an operation with its metrics"""
        with self.metrics_lock:
            if operation_name not in self.operation_metrics:
                self.operation_metrics[operation_name] = OperationMetric(operation_name)
            
            metric = self.operation_metrics[operation_name]
            metric.record_operation(duration, success, error)
            
            # Track slow operations
            if duration * 1000 > self.health_monitor.performance_thresholds['slow_operation_ms']:
                self.slow_operations.append({
                    'operation': operation_name,
                    'duration_ms': round(duration * 1000, 2),
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'metadata': metadata or {}
                })
            
            # Log significant errors
            if not success:
                logger.warning(f"Operation {operation_name} failed: {error}")
    
    def record_buffer_operation(self, operation_type: str, buffer_state: Dict):
        """Record buffer-specific operations"""
        with self.metrics_lock:
            if operation_type == 'add':
                self.buffer_metrics.total_adds += 1
            elif operation_type == 'recall':
                self.buffer_metrics.total_recalls += 1
            elif operation_type == 'search':
                self.buffer_metrics.total_searches += 1
            elif operation_type == 'eviction':
                self.buffer_metrics.total_evictions += 1
            elif operation_type == 'archive':
                self.buffer_metrics.total_archives += 1
            
            # Update buffer state
            self.buffer_metrics.record_buffer_state(
                buffer_state.get('current_size', 0),
                buffer_state.get('max_size', 20)
            )
    
    def record_custom_metric(self, category: str, metric_name: str, value: float):
        """Record a custom metric"""
        with self.metrics_lock:
            self.custom_metrics[category][metric_name] = value
    
    def increment_custom_metric(self, category: str, metric_name: str, increment: float = 1.0):
        """Increment a custom metric"""
        with self.metrics_lock:
            self.custom_metrics[category][metric_name] += increment
    
    def record_memory_integrity_event(self, event_type: str, metadata: Dict = None):
        """Record memory integrity events"""
        with self.metrics_lock:
            if event_type == 'validation_request':
                self.memory_integrity_metrics['validation_requests'] += 1
            elif event_type == 'validation_failure':
                self.memory_integrity_metrics['validation_failures'] += 1
            elif event_type == 'contradiction_found':
                self.memory_integrity_metrics['contradictions_found'] += 1
            elif event_type == 'context_violation':
                self.memory_integrity_metrics['context_violations'] += 1
            elif event_type == 'cross_conversation_bleed':
                self.memory_integrity_metrics['cross_conversation_bleeds'] += 1
            elif event_type == 'uncertainty_flag':
                self.memory_integrity_metrics['uncertainty_flags'] += 1
            
            logger.info(f"Memory integrity event: {event_type}", extra={"metadata": metadata})
    
    def record_retrieval_confidence(self, confidence_score: float):
        """Record retrieval confidence scores for accuracy tracking"""
        with self.metrics_lock:
            self.memory_integrity_metrics['retrieval_confidence_total'] += confidence_score
            self.memory_integrity_metrics['retrieval_confidence_count'] += 1
    
    def take_metrics_snapshot(self):
        """Take a snapshot of current metrics"""
        with self.metrics_lock:
            snapshot = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'uptime_seconds': (datetime.now(timezone.utc) - self.start_time).total_seconds(),
                'operations': {
                    name: metric.get_stats()
                    for name, metric in self.operation_metrics.items()
                },
                'buffer_metrics': {
                    'total_adds': self.buffer_metrics.total_adds,
                    'total_recalls': self.buffer_metrics.total_recalls,
                    'total_searches': self.buffer_metrics.total_searches,
                    'total_evictions': self.buffer_metrics.total_evictions,
                    'total_archives': self.buffer_metrics.total_archives,
                    'buffer_full_events': self.buffer_metrics.buffer_full_events,
                    'max_utilization': round(self.buffer_metrics.max_buffer_utilization * 100, 2),
                    'current_size': self.buffer_metrics.current_buffer_size,
                    'recent_utilization': list(self.buffer_metrics.buffer_size_history)[-10:]
                },
                'memory_integrity': {
                    'validation_requests': self.memory_integrity_metrics['validation_requests'],
                    'validation_failures': self.memory_integrity_metrics['validation_failures'],
                    'contradictions_found': self.memory_integrity_metrics['contradictions_found'],
                    'context_violations': self.memory_integrity_metrics['context_violations'],
                    'cross_conversation_bleeds': self.memory_integrity_metrics['cross_conversation_bleeds'],
                    'uncertainty_flags': self.memory_integrity_metrics['uncertainty_flags'],
                    'average_retrieval_confidence': (
                        self.memory_integrity_metrics['retrieval_confidence_total'] / 
                        max(self.memory_integrity_metrics['retrieval_confidence_count'], 1)
                    )
                },
                'custom_metrics': dict(self.custom_metrics),
                'health': self.health_monitor.check_health({
                    'operations': {
                        name: metric.get_stats()
                        for name, metric in self.operation_metrics.items()
                    },
                    'buffer_metrics': {
                        'current_size': self.buffer_metrics.current_buffer_size,
                        'max_size': 20  # Default, should be passed in
                    }
                })
            }
            
            self.metrics_history.append(snapshot)
            return snapshot
    
    def get_performance_summary(self) -> Dict:
        """Get performance summary statistics"""
        with self.metrics_lock:
            total_operations = sum(m.count for m in self.operation_metrics.values())
            total_errors = sum(m.error_count for m in self.operation_metrics.values())
            
            # Calculate percentiles from recent operations
            all_durations = []
            for metric in self.operation_metrics.values():
                if metric.count > 0:
                    avg_duration = metric.total_duration / metric.count
                    all_durations.extend([avg_duration] * min(metric.count, 10))
            
            all_durations.sort()
            
            if all_durations:
                p50 = all_durations[len(all_durations) // 2]
                p95 = all_durations[int(len(all_durations) * 0.95)]
                p99 = all_durations[int(len(all_durations) * 0.99)]
            else:
                p50 = p95 = p99 = 0
            
            return {
                'total_operations': total_operations,
                'total_errors': total_errors,
                'overall_error_rate': round(total_errors / total_operations * 100, 2) if total_operations > 0 else 0,
                'response_time_percentiles_ms': {
                    'p50': round(p50 * 1000, 2),
                    'p95': round(p95 * 1000, 2),
                    'p99': round(p99 * 1000, 2)
                },
                'slow_operations_count': len(self.slow_operations),
                'recent_slow_operations': list(self.slow_operations)[-5:],
                'uptime_hours': round((datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600, 2)
            }
    
    def get_buffer_analytics(self) -> Dict:
        """Get detailed buffer analytics"""
        with self.metrics_lock:
            # Calculate rates
            uptime_hours = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
            
            return {
                'operation_counts': {
                    'adds': self.buffer_metrics.total_adds,
                    'recalls': self.buffer_metrics.total_recalls,
                    'searches': self.buffer_metrics.total_searches,
                    'evictions': self.buffer_metrics.total_evictions,
                    'archives': self.buffer_metrics.total_archives
                },
                'operation_rates_per_hour': {
                    'adds': round(self.buffer_metrics.total_adds / uptime_hours, 2) if uptime_hours > 0 else 0,
                    'recalls': round(self.buffer_metrics.total_recalls / uptime_hours, 2) if uptime_hours > 0 else 0,
                    'searches': round(self.buffer_metrics.total_searches / uptime_hours, 2) if uptime_hours > 0 else 0
                },
                'buffer_pressure': {
                    'full_events': self.buffer_metrics.buffer_full_events,
                    'max_utilization_percent': round(self.buffer_metrics.max_buffer_utilization * 100, 2),
                    'current_utilization': self.buffer_metrics.buffer_size_history[-1] if self.buffer_metrics.buffer_size_history else None
                },
                'efficiency_metrics': {
                    'hit_rate': round(self.buffer_metrics.total_recalls / (self.buffer_metrics.total_recalls + self.buffer_metrics.total_searches) * 100, 2) 
                               if (self.buffer_metrics.total_recalls + self.buffer_metrics.total_searches) > 0 else 0,
                    'eviction_rate': round(self.buffer_metrics.total_evictions / self.buffer_metrics.total_adds * 100, 2)
                                    if self.buffer_metrics.total_adds > 0 else 0
                }
            }
    
    def export_metrics(self, format: str = 'json') -> str:
        """Export metrics in specified format"""
        snapshot = self.take_metrics_snapshot()
        
        if format == 'json':
            return json.dumps(snapshot, indent=2)
        elif format == 'prometheus':
            # Prometheus format for scraping
            lines = []
            lines.append(f"# HELP working_memory_uptime_seconds Working memory service uptime")
            lines.append(f"# TYPE working_memory_uptime_seconds counter")
            lines.append(f"working_memory_uptime_seconds {snapshot['uptime_seconds']}")
            
            # Operation metrics
            for op_name, op_stats in snapshot['operations'].items():
                safe_name = op_name.replace(' ', '_').replace('-', '_')
                lines.append(f"# HELP working_memory_operation_{safe_name}_total Total {op_name} operations")
                lines.append(f"# TYPE working_memory_operation_{safe_name}_total counter")
                lines.append(f"working_memory_operation_{safe_name}_total {op_stats['count']}")
                
                lines.append(f"# HELP working_memory_operation_{safe_name}_duration_seconds {op_name} operation duration")
                lines.append(f"# TYPE working_memory_operation_{safe_name}_duration_seconds summary")
                lines.append(f"working_memory_operation_{safe_name}_duration_seconds_sum {op_stats['total_duration_s']}")
                lines.append(f"working_memory_operation_{safe_name}_duration_seconds_count {op_stats['count']}")
            
            # Buffer metrics
            buffer_metrics = snapshot['buffer_metrics']
            lines.append(f"# HELP working_memory_buffer_size Current buffer size")
            lines.append(f"# TYPE working_memory_buffer_size gauge")
            lines.append(f"working_memory_buffer_size {buffer_metrics['current_size']}")
            
            lines.append(f"# HELP working_memory_buffer_operations_total Buffer operations by type")
            lines.append(f"# TYPE working_memory_buffer_operations_total counter")
            lines.append(f'working_memory_buffer_operations_total{{type="add"}} {buffer_metrics["total_adds"]}')
            lines.append(f'working_memory_buffer_operations_total{{type="recall"}} {buffer_metrics["total_recalls"]}')
            lines.append(f'working_memory_buffer_operations_total{{type="search"}} {buffer_metrics["total_searches"]}')
            
            return '\n'.join(lines)
        else:
            return json.dumps(snapshot, indent=2)  # Default to JSON
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)"""
        with self.metrics_lock:
            self.operation_metrics.clear()
            self.buffer_metrics = BufferMetrics()
            self.custom_metrics.clear()
            self.metrics_history.clear()
            self.slow_operations.clear()
            self.start_time = datetime.now(timezone.utc)
            logger.info("Metrics reset")
    
    def get_observability_status(self) -> Dict:
        """Get overall observability system status"""
        return {
            'status': 'operational',
            'tracking_operations': len(self.operation_metrics),
            'metrics_history_size': len(self.metrics_history),
            'custom_metrics_categories': list(self.custom_metrics.keys()),
            'health_status': self.health_monitor.check_health({
                'operations': {
                    name: metric.get_stats()
                    for name, metric in self.operation_metrics.items()
                },
                'buffer_metrics': {
                    'current_size': self.buffer_metrics.current_buffer_size,
                    'max_size': 20
                }
            }),
            'recent_alerts': self.health_monitor.get_recent_alerts(5)
        }