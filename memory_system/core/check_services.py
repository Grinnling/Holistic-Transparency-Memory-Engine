#!/usr/bin/env python3
"""
check_services.py - System Health Validator

Reads configuration from .env and validates all services are reachable.
Provides a quick "system at a glance" view.

Usage:
    python3 check_services.py          # Check all services
    python3 check_services.py --quick  # Quick check (shorter timeouts)
    python3 check_services.py --json   # Output as JSON for scripting

For Claude/AI: Run this to understand current system state before debugging.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error
import socket


@dataclass
class ServiceConfig:
    """Configuration for a single service."""
    name: str
    env_var: str
    default_url: str
    health_path: str = "/health"
    description: str = ""
    required: bool = True


# Service definitions - the system topology
SERVICES = [
    # Core API
    ServiceConfig(
        name="Main API",
        env_var="VITE_API_URL",
        default_url="http://localhost:8000",
        health_path="/health",
        description="FastAPI server - chat, memory, services",
        required=True
    ),

    # Memory System
    ServiceConfig(
        name="Working Memory",
        env_var="WORKING_MEMORY_URL",
        default_url="http://localhost:5001",
        health_path="/health",
        description="Short-term conversation context",
        required=True
    ),
    ServiceConfig(
        name="Episodic Memory",
        env_var="EPISODIC_MEMORY_URL",
        default_url="http://localhost:8005",
        health_path="/health",
        description="Long-term vector storage",
        required=True
    ),
    ServiceConfig(
        name="Curator",
        env_var="CURATOR_URL",
        default_url="http://localhost:8004",
        health_path="/health",
        description="Memory curation and ranking",
        required=False
    ),
    ServiceConfig(
        name="MCP Logger",
        env_var="MCP_LOGGER_URL",
        default_url="http://localhost:8001",
        health_path="/health",
        description="MCP operation logging",
        required=False
    ),

    # LLM Backends - defined but filtered dynamically based on LLM_BACKEND setting
    ServiceConfig(
        name="LM Studio",
        env_var="LMSTUDIO_URL",
        default_url="http://localhost:1234",
        health_path="/v1/models",  # OpenAI-compatible endpoint
        description="Local LLM with model stacking",
        required=False
    ),
    ServiceConfig(
        name="Ollama",
        env_var="OLLAMA_URL",
        default_url="http://localhost:11434",
        health_path="/api/tags",  # Ollama's health-like endpoint
        description="Local LLM runner",
        required=False
    ),
    ServiceConfig(
        name="TextGen WebUI",
        env_var="TEXTGEN_URL",
        default_url="http://localhost:8080",
        health_path="/api/v1/model",  # TGI health endpoint
        description="Text Generation WebUI",
        required=False
    ),

    # Optional
    ServiceConfig(
        name="Redis",
        env_var="REDIS_URL",
        default_url="redis://localhost:6379/0",
        health_path="",  # Redis uses different protocol
        description="Context registry cache",
        required=False
    ),
]


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}

    if not env_path.exists():
        return env_vars

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Parse KEY=value
            if '=' in line:
                key, _, value = line.partition('=')
                env_vars[key.strip()] = value.strip()

    return env_vars


def check_http_service(url: str, health_path: str, timeout: float) -> Tuple[bool, str]:
    """Check if an HTTP service is reachable."""
    try:
        full_url = url.rstrip('/') + health_path
        req = urllib.request.Request(full_url, method='GET')
        req.add_header('User-Agent', 'check_services/1.0')

        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                return True, f"OK ({response.status})"
            else:
                return False, f"HTTP {response.status}"

    except urllib.error.HTTPError as e:
        # Some services return non-200 but are still "up"
        if e.code in (401, 403, 404, 405):
            return True, f"Up (HTTP {e.code})"
        return False, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return False, f"Unreachable: {e.reason}"
    except socket.timeout:
        return False, "Timeout"
    except Exception as e:
        return False, f"Error: {str(e)[:30]}"


def check_redis(url: str, timeout: float) -> Tuple[bool, str]:
    """Check if Redis is reachable."""
    try:
        # Parse redis URL: redis://host:port/db
        if url.startswith('redis://'):
            url = url[8:]

        # Remove db number if present
        if '/' in url:
            url = url.split('/')[0]

        # Parse host:port
        if ':' in url:
            host, port_str = url.split(':')
            port = int(port_str)
        else:
            host = url
            port = 6379

        # Try to connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            return True, "OK (port open)"
        else:
            return False, "Port closed"

    except Exception as e:
        return False, f"Error: {str(e)[:30]}"


def check_service(service: ServiceConfig, env_vars: Dict[str, str], timeout: float) -> Dict:
    """Check a single service and return status."""
    # Get URL from env or use default
    url = env_vars.get(service.env_var) or os.environ.get(service.env_var) or service.default_url

    # Check based on protocol
    if url.startswith('redis://'):
        is_up, status = check_redis(url, timeout)
    else:
        is_up, status = check_http_service(url, service.health_path, timeout)

    return {
        "name": service.name,
        "url": url,
        "status": status,
        "is_up": is_up,
        "required": service.required,
        "description": service.description
    }


def print_results(results: list, show_description: bool = True):
    """Print results as a formatted table."""
    # Determine column widths
    name_width = max(len(r["name"]) for r in results) + 2
    url_width = max(len(r["url"]) for r in results) + 2
    status_width = max(len(r["status"]) for r in results) + 2

    # Header
    print("\n" + "=" * 70)
    print("  SYSTEM SERVICE STATUS")
    print("=" * 70)

    # Results
    up_count = 0
    down_required = []

    for r in results:
        # Status indicator
        if r["is_up"]:
            indicator = "\033[92m[UP]\033[0m"  # Green
            up_count += 1
        elif r["required"]:
            indicator = "\033[91m[DOWN]\033[0m"  # Red
            down_required.append(r["name"])
        else:
            indicator = "\033[93m[OFF]\033[0m"  # Yellow (optional)

        # Required marker
        req_marker = "*" if r["required"] else " "

        print(f"  {indicator} {req_marker}{r['name']:<{name_width}} {r['url']:<{url_width}} {r['status']}")

        if show_description and r["description"]:
            print(f"         {r['description']}")

    # Summary
    print("-" * 70)
    print(f"  {up_count}/{len(results)} services responding")
    print("  * = required service")

    if down_required:
        print(f"\n  \033[91mWARNING: Required services down: {', '.join(down_required)}\033[0m")
    else:
        print(f"\n  \033[92mAll required services operational.\033[0m")

    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Check system service health")
    parser.add_argument("--quick", action="store_true", help="Quick check with short timeouts")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-desc", action="store_true", help="Hide service descriptions")
    parser.add_argument("--env", type=str, default=".env", help="Path to .env file")
    args = parser.parse_args()

    # Load environment
    env_path = Path(__file__).parent / args.env
    env_vars = load_env_file(env_path)

    # Set timeout
    timeout = 1.0 if args.quick else 3.0

    # Filter services - only check the configured LLM backend
    llm_backend = env_vars.get('LLM_BACKEND', os.environ.get('LLM_BACKEND', 'lmstudio')).lower()
    llm_env_map = {
        'lmstudio': 'LMSTUDIO_URL',
        'ollama': 'OLLAMA_URL',
        'textgen': 'TEXTGEN_URL',
        'tgi': 'TEXTGEN_URL',
    }
    active_llm_env = llm_env_map.get(llm_backend)

    # Only include the configured LLM backend
    services_to_check = [
        svc for svc in SERVICES
        if svc.env_var not in ['LMSTUDIO_URL', 'OLLAMA_URL', 'TEXTGEN_URL']  # Non-LLM services
        or svc.env_var == active_llm_env  # Or the configured LLM backend
    ]

    # Check services in parallel
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {
            executor.submit(check_service, svc, env_vars, timeout): svc
            for svc in services_to_check
        }

        for future in as_completed(future_to_service):
            results.append(future.result())

    # Sort by required status then name
    results.sort(key=lambda x: (not x["required"], x["name"]))

    # Output
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_results(results, show_description=not args.no_desc)

    # Exit code: 0 if all required services up, 1 otherwise
    required_down = any(not r["is_up"] and r["required"] for r in results)
    sys.exit(1 if required_down else 0)


if __name__ == "__main__":
    main()
