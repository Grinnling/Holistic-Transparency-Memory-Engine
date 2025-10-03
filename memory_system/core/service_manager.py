#!/usr/bin/env python3
"""
ServiceManager - Extracted service management from rich_chat.py
Handles service health checking, auto-starting, and lifecycle management
Part of Phase 2 refactoring to reduce monolithic class complexity
"""

import os
import time
import signal
import requests
import subprocess
from typing import Dict, Optional, List, Any
from rich.table import Table
from rich.console import Console
from error_handler import ErrorHandler, ErrorCategory, ErrorSeverity

class ServiceManager:
    """Manages microservice lifecycle - health checking, starting, stopping"""

    def __init__(self, console: Console = None, error_handler: ErrorHandler = None, debug_mode: bool = False):
        """
        Initialize ServiceManager with necessary dependencies

        Args:
            console: Rich console for output (optional, creates new if not provided)
            error_handler: Error handler for centralized error management
            debug_mode: Enable debug output
        """
        self.console = console or Console()
        self.error_handler = error_handler or ErrorHandler(console=self.console, debug_mode=debug_mode)
        self.debug_mode = debug_mode

        # Service configuration
        self.services = {
            'working_memory': 'http://localhost:5001',
            'curator': 'http://localhost:8004',
            'mcp_logger': 'http://localhost:8001',
            'episodic_memory': 'http://localhost:8005'
        }

        # Service process tracking
        self.service_processes = {}

        # Service health tracking for {ME} - helps understand patterns
        self.health_history = {}
        self.restart_attempts = {}

        # Service dependencies for {ME} - helps with startup order
        self.service_dependencies = {
            'episodic_memory': ['working_memory'],  # Episodic needs working memory
            'curator': ['working_memory'],          # Curator needs working memory
            'mcp_logger': [],                        # Independent
            'working_memory': []                     # Independent
        }

        # Service groups for {YOU} - easier management
        self.service_groups = {
            'memory_system': ['working_memory', 'episodic_memory', 'curator'],
            'logging': ['mcp_logger'],
            'all': list(self.services.keys())
        }

        # Base path for services
        self.base_path = '/home/grinnling/Development/ACTIVE_SERVICES/docker_agent_environment/memory_system'

        # Service configurations
        self.service_configs = {
            'working_memory': {
                'path': f'{self.base_path}/working_memory',
                'file': 'service.py',
                'port': 5001
            },
            'curator': {
                'path': f'{self.base_path}/memory_curator',
                'file': 'curator_service.py',
                'port': 8004
            },
            'mcp_logger': {
                'path': f'{self.base_path}/mcp_logger',
                'file': 'server.py',
                'port': 8001
            },
            'episodic_memory': {
                'path': f'{self.base_path}/episodic_memory',
                'file': 'service.py',
                'port': 8005
            }
        }

    def check_services(self, show_table: bool = True, include_extras: Dict[str, str] = None) -> bool:
        """
        Check health of all services

        Args:
            show_table: Whether to display the status table
            include_extras: Additional services to check (e.g., {'LLM': 'Connected'})

        Returns:
            bool: True if all services are healthy
        """
        if show_table:
            table = Table(title="🔍 Service Health Check")
            table.add_column("Service", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details", style="dim")

        all_healthy = True
        service_status = {}

        for service_name, url in self.services.items():
            try:
                with self.error_handler.create_context_manager(
                    ErrorCategory.SERVICE_HEALTH,
                    ErrorSeverity.LOW_DEBUG,
                    operation=f"health_check_{service_name}",
                    context=f"Checking {service_name}"
                ):
                    response = requests.get(f"{url}/health", timeout=2)
                    if response.status_code == 200:
                        service_status[service_name] = "healthy"
                        if show_table:
                            table.add_row(service_name, "✅ Online", url)
                    else:
                        service_status[service_name] = "unhealthy"
                        all_healthy = False
                        if show_table:
                            table.add_row(service_name, "❌ Error", f"HTTP {response.status_code}")
            except Exception as e:
                service_status[service_name] = "offline"
                all_healthy = False
                if show_table:
                    table.add_row(service_name, "❌ Offline", url)

                # Log the error but don't spam
                self.error_handler.handle_error(
                    e,
                    ErrorCategory.SERVICE_CONNECTION,
                    ErrorSeverity.LOW_DEBUG,
                    context=f"{service_name} health check",
                    operation="health_check",
                    suppress_duplicate_minutes=5
                )

        # Add extra services if provided (like LLM, Skinflap)
        if include_extras and show_table:
            for name, status_info in include_extras.items():
                table.add_row(name, status_info[0], status_info[1])

        if show_table:
            self.console.print(table)

        return all_healthy

    def check_service_health(self, service_name: str) -> str:
        """
        Check health of a specific service

        Args:
            service_name: Name of the service to check

        Returns:
            str: 'healthy', 'unhealthy', or 'offline'
        """
        if service_name not in self.services:
            return 'unknown'

        url = self.services[service_name]
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                return 'healthy'
            else:
                return 'unhealthy'
        except:
            return 'offline'

    def auto_start_services(self) -> bool:
        """
        Automatically start services that are not running

        Returns:
            bool: True if all services are running after startup attempts
        """
        self._info_message("🔍 Checking services...")
        services_to_start = []

        # Check each service
        for name, url in self.services.items():
            try:
                response = requests.get(f"{url}/health", timeout=1)
                if response.status_code == 200:
                    self._debug_message(f"✅ {name} already running")
                else:
                    services_to_start.append(name)
            except:
                services_to_start.append(name)

        if not services_to_start:
            self._success_message("All services already running!")
            return True

        # Start missing services
        self._info_message(f"Starting {len(services_to_start)} services...")

        for service in services_to_start:
            if service in self.service_configs:
                self._start_service(service)

        # Wait for services to initialize
        if services_to_start:
            self._info_message("Waiting for services to initialize...")
            time.sleep(5)

            # Verify they started
            return self.verify_services_running(services_to_start)

        return True

    def _start_service(self, service: str) -> bool:
        """
        Start a specific service

        Args:
            service: Name of the service to start

        Returns:
            bool: True if service started successfully
        """
        if service not in self.service_configs:
            self._error_message(f"Unknown service: {service}")
            return False

        config = self.service_configs[service]
        service_path = config['path']
        service_file = config['file']
        port = config['port']

        self._info_message(f"🚀 Starting {service} on port {port}...")

        try:
            # Create log directory
            log_dir = "/tmp/rich_chat_services"
            os.makedirs(log_dir, exist_ok=True)

            stdout_log = f"{log_dir}/{service}_stdout.log"
            stderr_log = f"{log_dir}/{service}_stderr.log"

            # Create environment for the service
            service_env = {**os.environ}
            service_env[f'{service.upper()}_PORT'] = str(port)

            if self.debug_mode:
                service_env['DEBUG'] = '1'
                self._debug_message(f"Starting in {service_path}")
                self._debug_message(f"Running {service_file}")

            # Start the service process
            process = subprocess.Popen(
                ['python3', service_file],
                cwd=service_path,
                stdout=open(stdout_log, 'w'),
                stderr=open(stderr_log, 'w'),
                start_new_session=True,
                env=service_env
            )

            self.service_processes[service] = process
            self._success_message(f"✅ Started {service} (PID: {process.pid})")

            if self.debug_mode:
                self._debug_message(f"Logs: {stdout_log}")
                self._debug_message(f"Errors: {stderr_log}")

            return True

        except Exception as e:
            self.error_handler.handle_error(
                e,
                ErrorCategory.AUTO_START,
                ErrorSeverity.HIGH_DEGRADE,
                context=f"Starting {service}",
                operation="service_startup"
            )
            return False

    def verify_services_running(self, services: List[str] = None) -> bool:
        """
        Verify that services are actually running

        Args:
            services: List of service names to check (or all if None)

        Returns:
            bool: True if all specified services are running
        """
        if services is None:
            services = list(self.services.keys())

        all_running = True
        for service in services:
            status = self.check_service_health(service)
            if status != 'healthy':
                self._warning_message(f"⚠️ {service} failed to start properly")
                all_running = False
            else:
                self._success_message(f"✅ {service} verified running")

        return all_running

    def stop_service(self, service: str) -> bool:
        """
        Stop a specific service

        Args:
            service: Name of the service to stop

        Returns:
            bool: True if service stopped successfully
        """
        if service in self.service_processes:
            process = self.service_processes[service]
            if process.poll() is None:  # Still running
                self._info_message(f"Stopping {service} (PID: {process.pid})...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                del self.service_processes[service]
                self._success_message(f"✅ Stopped {service}")
                return True
        return False

    def stop_all_services(self):
        """Stop all managed services"""
        self._info_message("Stopping all services...")
        for service in list(self.service_processes.keys()):
            self.stop_service(service)

    def cleanup(self):
        """Clean up resources and stop services"""
        self.stop_all_services()

    # Enhanced methods for {US} - Better collaboration

    def get_service_health_detailed(self, service_name: str) -> Dict[str, Any]:
        """
        Get detailed health information for {ME} to better understand issues

        Returns comprehensive health data including history and suggestions
        """
        from datetime import datetime

        status = self.check_service_health(service_name)

        # Track health history for pattern detection
        if service_name not in self.health_history:
            self.health_history[service_name] = []

        health_record = {
            'timestamp': datetime.now().isoformat(),
            'status': status,
            'checks_performed': len(self.health_history.get(service_name, [])) + 1
        }

        # Calculate health metrics
        history = self.health_history.get(service_name, [])[-10:]  # Last 10 checks
        if history:
            failure_rate = sum(1 for h in history if h.get('status') != 'healthy') / len(history)
        else:
            failure_rate = 0

        # Provide actionable suggestions for {YOU}
        suggested_action = None
        if status == 'offline':
            suggested_action = 'Service is down. Run auto_start_services() to restart.'
        elif status == 'unhealthy':
            suggested_action = 'Service responding but unhealthy. Check logs for errors.'
        elif failure_rate > 0.3:
            suggested_action = f'High failure rate ({failure_rate:.0%}). Consider investigation.'

        self.health_history[service_name].append(health_record)

        return {
            'service': service_name,
            'status': status,
            'failure_rate': failure_rate,
            'total_checks': len(self.health_history.get(service_name, [])),
            'restart_attempts': self.restart_attempts.get(service_name, 0),
            'suggested_action': suggested_action,
            'dependencies': self.service_dependencies.get(service_name, []),
            'dependent_services': [s for s, deps in self.service_dependencies.items() if service_name in deps]
        }

    def smart_recovery(self, service_name: str) -> bool:
        """
        Intelligent recovery that helps {ME} learn what works

        Tries progressive recovery strategies and tracks what succeeds
        """
        if service_name not in self.services:
            self._error_message(f"Unknown service: {service_name}")
            return False

        # Track restart attempts for {ME} to learn patterns
        if service_name not in self.restart_attempts:
            self.restart_attempts[service_name] = 0
        self.restart_attempts[service_name] += 1

        self._info_message(f"🔧 Attempting smart recovery for {service_name} (attempt #{self.restart_attempts[service_name]})")

        # Progressive recovery strategies
        strategies = [
            ('check_dependencies', lambda: self._ensure_dependencies_running(service_name)),
            ('gentle_restart', lambda: self._gentle_restart(service_name)),
            ('force_restart', lambda: self._force_restart(service_name)),
            ('clean_restart', lambda: self._clean_restart(service_name))
        ]

        for strategy_name, strategy_func in strategies:
            self._info_message(f"  Trying strategy: {strategy_name}")
            try:
                if strategy_func():
                    self._success_message(f"✅ Recovery successful using {strategy_name}")
                    # Track successful strategy for {ME} to learn
                    if service_name not in self.health_history:
                        self.health_history[service_name] = []
                    self.health_history[service_name].append({
                        'recovery_strategy': strategy_name,
                        'success': True
                    })
                    return True
            except Exception as e:
                self._debug_message(f"Strategy {strategy_name} failed: {e}")

        self._error_message(f"❌ All recovery strategies failed for {service_name}")
        return False

    def _ensure_dependencies_running(self, service: str) -> bool:
        """Ensure all dependencies are running first"""
        deps = self.service_dependencies.get(service, [])
        if not deps:
            return False

        all_deps_healthy = True
        for dep in deps:
            if self.check_service_health(dep) != 'healthy':
                self._info_message(f"    Starting dependency: {dep}")
                if not self._start_service(dep):
                    all_deps_healthy = False

        if all_deps_healthy:
            time.sleep(2)  # Give dependencies time to stabilize
            return self._start_service(service)
        return False

    def _gentle_restart(self, service: str) -> bool:
        """Stop and start with a pause"""
        self.stop_service(service)
        time.sleep(3)
        return self._start_service(service)

    def _force_restart(self, service: str) -> bool:
        """Kill and restart immediately"""
        if service in self.service_processes:
            process = self.service_processes[service]
            if process.poll() is None:
                process.kill()
                process.wait()
        return self._start_service(service)

    def _clean_restart(self, service: str) -> bool:
        """Clear logs and restart fresh"""
        log_dir = "/tmp/rich_chat_services"
        if os.path.exists(log_dir):
            import glob
            for log_file in glob.glob(f"{log_dir}/{service}*.log"):
                try:
                    os.remove(log_file)
                except:
                    pass
        return self._start_service(service)

    def start_group(self, group_name: str) -> bool:
        """
        Start a group of related services for {YOU}

        Makes it easy to start logical groups like 'memory_system'
        """
        if group_name not in self.service_groups:
            self._error_message(f"Unknown service group: {group_name}")
            self._info_message(f"Available groups: {list(self.service_groups.keys())}")
            return False

        services = self.service_groups[group_name]
        self._info_message(f"Starting service group '{group_name}': {services}")

        # Sort by dependencies for correct startup order
        sorted_services = self._sort_by_dependencies(services)

        success = True
        for service in sorted_services:
            if not self._start_service(service):
                success = False
                self._warning_message(f"Failed to start {service}")

        return success

    def _sort_by_dependencies(self, services: List[str]) -> List[str]:
        """Sort services by dependency order for {ME} to start correctly"""
        sorted_list = []
        remaining = set(services)

        while remaining:
            # Find services with no dependencies in remaining set
            ready = [s for s in remaining
                    if not any(d in remaining for d in self.service_dependencies.get(s, []))]

            if not ready:
                # Circular dependency or missing dependency
                self._warning_message(f"Dependency issue with services: {remaining}")
                sorted_list.extend(list(remaining))
                break

            sorted_list.extend(ready)
            remaining -= set(ready)

        return sorted_list

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive service data for {YOU}'s React dashboard

        Returns data perfect for the React frontend status panel
        """
        dashboard = {}
        for service in self.services:
            health_data = self.get_service_health_detailed(service)
            dashboard[service] = {
                'status': health_data['status'],
                'health_score': 100 * (1 - health_data['failure_rate']),
                'restart_count': health_data['restart_attempts'],
                'suggestion': health_data['suggested_action'],
                'dependencies': health_data['dependencies'],
                'url': self.services[service]
            }

        # Add summary for {YOU}
        dashboard['_summary'] = {
            'total_services': len(self.services),
            'healthy_count': sum(1 for s in dashboard.values() if isinstance(s, dict) and s.get('status') == 'healthy'),
            'groups': list(self.service_groups.keys()),
            'last_check': time.strftime('%Y-%m-%d %H:%M:%S')
        }

        return dashboard

    # Message helper methods
    def _info_message(self, msg: str):
        """Display info message"""
        if self.console:
            self.console.print(f"[blue]ℹ {msg}[/blue]")

    def _success_message(self, msg: str):
        """Display success message"""
        if self.console:
            self.console.print(f"[green]{msg}[/green]")

    def _warning_message(self, msg: str):
        """Display warning message"""
        if self.console:
            self.console.print(f"[yellow]{msg}[/yellow]")

    def _error_message(self, msg: str):
        """Display error message"""
        if self.console:
            self.console.print(f"[red]{msg}[/red]")

    def _debug_message(self, msg: str):
        """Display debug message if in debug mode"""
        if self.debug_mode and self.console:
            self.console.print(f"[dim]DEBUG: {msg}[/dim]")


# Convenience functions for standalone usage
def check_all_services(debug: bool = False) -> bool:
    """Quick function to check all services"""
    manager = ServiceManager(debug_mode=debug)
    return manager.check_services()


def auto_start_all_services(debug: bool = False) -> bool:
    """Quick function to auto-start all services"""
    manager = ServiceManager(debug_mode=debug)
    return manager.auto_start_services()


if __name__ == "__main__":
    # Test the service manager
    import sys
    debug = "--debug" in sys.argv

    manager = ServiceManager(debug_mode=debug)

    print("\n=== Testing Service Manager ===\n")

    # Check services
    print("1. Checking service health...")
    all_healthy = manager.check_services()
    print(f"   All services healthy: {all_healthy}")

    # Auto-start if needed
    if "--autostart" in sys.argv and not all_healthy:
        print("\n2. Auto-starting services...")
        success = manager.auto_start_services()
        print(f"   Auto-start successful: {success}")

    print("\n=== Service Manager Test Complete ===")