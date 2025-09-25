#!/usr/bin/env python3
"""
Kuzu Server Manager

Manages the Kuzu Neo4j server as a background process, including starting,
stopping, and restarting during database rebuilds.
"""

import os
import sys
import time
import signal
import subprocess
import threading
import psutil
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console

console = Console()

class KuzuServerManager:
    """Manages the Kuzu Neo4j server process"""
    
    def __init__(self, db_path: str, port: int = 7001, host: str = "0.0.0.0"):
        self.db_path = Path(db_path)
        self.port = port
        self.host = host
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._lock = threading.Lock()
        
    def start_server(self, force_restart: bool = False) -> bool:
        """Start the Kuzu server in the background"""
        with self._lock:
            if self.is_running and not force_restart:
                console.print("[yellow]Server is already running[/yellow]")
                return True
            
            # If force restart and server is running, stop it first
            if self.is_running and force_restart:
                console.print("[cyan]Force restarting server...[/cyan]")
                self.stop_server()
                
            try:
                # Check if port is already in use
                if self._is_port_in_use():
                    console.print(f"[red]Port {self.port} is already in use[/red]")
                    return False
                
                # Start the server process
                cmd = [
                    sys.executable, 
                    "kuzu_neo4j_server.py", 
                    str(self.db_path),
                    "--port", str(self.port),
                    "--host", self.host
                ]
                
                console.print(f"[cyan]Starting Kuzu server on {self.host}:{self.port}[/cyan]")
                
                # Start process in background (don't capture output to avoid hanging)
                self.process = subprocess.Popen(
                    cmd,
                    text=True,
                    cwd=Path(__file__).parent
                )
                
                # Wait a moment for the server to start
                time.sleep(2)
                
                # Check if process is still running
                if self.process.poll() is None:
                    self.is_running = True
                    console.print(f"[green]Kuzu server started successfully (PID: {self.process.pid})[/green]")
                    return True
                else:
                    console.print(f"[red]Failed to start Kuzu server[/red]")
                    console.print(f"Server process exited with code: {self.process.returncode}")
                    return False
                    
            except Exception as e:
                console.print(f"[red]Error starting Kuzu server: {e}[/red]")
                return False
    
    def stop_server(self) -> bool:
        """Stop the Kuzu server"""
        with self._lock:
            if not self.is_running or self.process is None:
                console.print("[yellow]Server is not running[/yellow]")
                return True
                
            try:
                console.print("[cyan]Stopping Kuzu server...[/cyan]")
                
                # Try graceful shutdown first
                self.process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if graceful shutdown fails
                    console.print("[yellow]Graceful shutdown timed out, forcing kill...[/yellow]")
                    self.process.kill()
                    self.process.wait()
                
                self.is_running = False
                self.process = None
                console.print("[green]Kuzu server stopped[/green]")
                return True
                
            except Exception as e:
                console.print(f"[red]Error stopping Kuzu server: {e}[/red]")
                return False
    
    def restart_server(self) -> bool:
        """Restart the Kuzu server"""
        console.print("[cyan]Restarting Kuzu server...[/cyan]")
        if self.stop_server():
            time.sleep(1)  # Brief pause before restart
            return self.start_server()
        return False
    
    def is_server_healthy(self) -> bool:
        """Check if the server is running and healthy"""
        if not self.is_running or self.process is None:
            return False
            
        # Check if process is still running
        if self.process.poll() is not None:
            self.is_running = False
            return False
            
        # Check if port is responding
        return self._is_port_in_use()
    
    def _is_port_in_use(self) -> bool:
        """Check if the port is in use"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == self.port and conn.status == 'LISTEN':
                    return True
            return False
        except Exception:
            return False
    
    def get_server_url(self) -> str:
        """Get the server URL"""
        return f"http://{self.host}:{self.port}"
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_server()
