"""
Kuzu Connection Pool with Server-Side Retry Logic

This module provides connection pooling and automatic retry mechanisms
for Kuzu database operations, handling database availability and
connection management.
"""

import asyncio
import os
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import kuzu
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

class DatabaseState(Enum):
    """Database availability states"""
    AVAILABLE = "available"
    UPDATING = "updating"
    LOCKED = "locked"
    UNAVAILABLE = "unavailable"

@dataclass
class PoolConfig:
    """Configuration for connection pool"""
    max_connections: int = 5
    max_retries: int = 3
    retry_delay: int = 10  # seconds
    connection_timeout: int = 30  # seconds
    idle_timeout: int = 300  # seconds (5 minutes)
    health_check_interval: int = 60  # seconds

class DatabaseAvailabilityChecker:
    """Checks database availability and handles retry logic"""
    
    def __init__(self, db_path: str, config: PoolConfig):
        self.db_path = db_path
        self.config = config
        self.last_check = 0
        self.cached_state = DatabaseState.UNAVAILABLE
        
    async def wait_for_database(self) -> bool:
        """Wait for database to become available with retry logic"""
        for attempt in range(self.config.max_retries):
            if await self.is_database_available():
                return True
                
            if attempt < self.config.max_retries - 1:
                console.print(f"[yellow]Database not available, waiting {self.config.retry_delay}s... (attempt {attempt + 1}/{self.config.max_retries})[/yellow]")
                await asyncio.sleep(self.config.retry_delay)
            else:
                console.print(f"[red]Database still not available after {self.config.max_retries} attempts[/red]")
                
        return False
        
    async def is_database_available(self) -> bool:
        """Check if database is available (with caching)"""
        current_time = time.time()
        
        # Use cached result if recent enough
        if current_time - self.last_check < 5:  # 5 second cache
            return self.cached_state == DatabaseState.AVAILABLE
            
        try:
            # Check if database file exists
            if not os.path.exists(self.db_path):
                self.cached_state = DatabaseState.UNAVAILABLE
                return False
                
            # Check if database is locked by another process
            if self._is_database_locked():
                self.cached_state = DatabaseState.LOCKED
                return False
                
            # Try to open a test connection
            if self._test_database_connection():
                self.cached_state = DatabaseState.AVAILABLE
                self.last_check = current_time
                return True
            else:
                self.cached_state = DatabaseState.UNAVAILABLE
                return False
                
        except Exception as e:
            logger.warning(f"Database check failed: {e}")
            self.cached_state = DatabaseState.UNAVAILABLE
            return False
            
    def _is_database_locked(self) -> bool:
        """Check if database is locked by another process"""
        try:
            # Check for lock files (Kuzu creates .lock files)
            lock_files = [
                f"{self.db_path}.lock",
                f"{self.db_path}.wal.lock",
                f"{self.db_path}.shm.lock"
            ]
            
            for lock_file in lock_files:
                if os.path.exists(lock_file):
                    return True
                    
            return False
            
        except Exception:
            return False
            
    def _test_database_connection(self) -> bool:
        """Test if we can actually connect to the database"""
        try:
            # Try to create a temporary connection
            database = kuzu.Database(self.db_path)
            conn = kuzu.Connection(database)
            # Test with a simple query
            result = conn.execute("MATCH (n) RETURN count(n) LIMIT 1")
            conn.close()
            return True
            
        except Exception as e:
            logger.debug(f"Database connection test failed: {e}")
            return False

class KuzuConnection:
    """Wrapper for Kuzu connection with metadata"""
    
    def __init__(self, connection: kuzu.Connection, created_at: float):
        self.connection = connection
        self.created_at = created_at
        self.last_used = created_at
        self.is_active = True
        
    def is_idle(self, idle_timeout: int) -> bool:
        """Check if connection has been idle too long"""
        return time.time() - self.last_used > idle_timeout
        
    def close(self):
        """Close the connection"""
        try:
            if self.connection:
                self.connection.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
        finally:
            self.is_active = False

class KuzuConnectionPool:
    """Connection pool for Kuzu database with retry logic"""
    
    def __init__(self, db_path: str, config: PoolConfig = None):
        self.db_path = db_path
        self.config = config or PoolConfig()
        self.availability_checker = DatabaseAvailabilityChecker(db_path, self.config)
        self.connections: List[KuzuConnection] = []
        self.lock = asyncio.Lock()
        self.health_check_task = None
        self.is_running = False
        
    async def start(self) -> bool:
        """Start the connection pool"""
        console.print("[cyan]Starting Kuzu connection pool...[/cyan]")
        
        # Wait for database to become available
        if not await self.availability_checker.wait_for_database():
            console.print("[red]Failed to start pool: Database not available[/red]")
            return False
            
        # Create initial connections
        await self._create_initial_connections()
        
        # Start health check task
        self.is_running = True
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        console.print(f"[green]Connection pool started with {len(self.connections)} connections[/green]")
        return True
        
    async def stop(self):
        """Stop the connection pool"""
        console.print("[cyan]Stopping Kuzu connection pool...[/cyan]")
        
        self.is_running = False
        
        # Cancel health check task
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
                
        # Close all connections
        async with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()
            
        console.print("[green]Connection pool stopped[/green]")
        
    async def get_connection(self) -> Optional[KuzuConnection]:
        """Get an available connection from the pool"""
        async with self.lock:
            # Find an available connection
            for conn in self.connections:
                if conn.is_active and not conn.is_idle(self.config.idle_timeout):
                    conn.last_used = time.time()
                    return conn
                    
            # No available connection, try to create a new one
            if len(self.connections) < self.config.max_connections:
                new_conn = await self._create_connection()
                if new_conn:
                    self.connections.append(new_conn)
                    return new_conn
                    
            return None
            
    async def release_connection(self, conn: KuzuConnection):
        """Release a connection back to the pool"""
        if conn and conn.is_active:
            conn.last_used = time.time()
            
    async def execute_query_with_retry(self, query: str) -> Dict[str, Any]:
        """Execute query with automatic retry if database becomes unavailable"""
        for attempt in range(self.config.max_retries):
            try:
                # Check if database is still available
                if not await self.availability_checker.is_database_available():
                    if attempt < self.config.max_retries - 1:
                        console.print(f"[yellow]Database unavailable, waiting {self.config.retry_delay}s... (attempt {attempt + 1}/{self.config.max_retries})[/yellow]")
                        await asyncio.sleep(self.config.retry_delay)
                        continue
                    else:
                        return {
                            "error": "Database unavailable",
                            "message": f"Database not available after {self.config.max_retries} attempts",
                            "retry_after": self.config.retry_delay
                        }
                
                # Get connection from pool
                conn = await self.get_connection()
                if not conn:
                    return {
                        "error": "No available connections",
                        "message": "All connections are busy or unavailable",
                        "retry_after": self.config.retry_delay
                    }
                
                try:
                    # Execute the query
                    result = conn.connection.execute(query)
                    
                    # Convert result to JSON-serializable format
                    formatted_result = self._format_query_result(result)
                    
                    # Release connection back to pool
                    await self.release_connection(conn)
                    
                    return formatted_result
                    
                except Exception as e:
                    # Connection might be bad, mark it as inactive
                    conn.is_active = False
                    await self.release_connection(conn)
                    
                    if attempt < self.config.max_retries - 1:
                        console.print(f"[yellow]Query failed, retrying in {self.config.retry_delay}s... (attempt {attempt + 1}/{self.config.max_retries})[/yellow]")
                        await asyncio.sleep(self.config.retry_delay)
                        continue
                    else:
                        return {
                            "error": "Query execution failed",
                            "message": str(e),
                            "retry_after": self.config.retry_delay
                        }
                        
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    console.print(f"[yellow]Query failed, retrying in {self.config.retry_delay}s... (attempt {attempt + 1}/{self.config.max_retries})[/yellow]")
                    await asyncio.sleep(self.config.retry_delay)
                    continue
                else:
                    return {
                        "error": "Query failed after retries",
                        "message": str(e),
                        "retry_after": self.config.retry_delay
                    }
                    
        return {
            "error": "Query failed after retries",
            "message": f"Query failed after {self.config.max_retries} attempts",
            "retry_after": self.config.retry_delay
        }
        
    async def _create_initial_connections(self):
        """Create initial connections for the pool"""
        initial_count = min(2, self.config.max_connections)  # Start with 2 connections
        
        for _ in range(initial_count):
            conn = await self._create_connection()
            if conn:
                self.connections.append(conn)
                
    async def _create_connection(self) -> Optional[KuzuConnection]:
        """Create a new Kuzu connection"""
        try:
            database = kuzu.Database(self.db_path)
            connection = kuzu.Connection(database)
            return KuzuConnection(connection, time.time())
        except Exception as e:
            logger.warning(f"Failed to create connection: {e}")
            return None
            
    def _format_query_result(self, result) -> Dict[str, Any]:
        """Format Kuzu query result for JSON response"""
        try:
            # Convert result to list of dictionaries
            columns = result.get_column_names()
            rows = []
            while result.has_next():
                row = result.get_next()
                # Convert to dictionary using column names
                row_dict = dict(zip(columns, row))
                rows.append(row_dict)
                
            return {
                "status": "success",
                "data": rows,
                "count": len(rows)
            }
            
        except Exception as e:
            return {
                "error": "Result formatting failed",
                "message": str(e)
            }
            
    async def _health_check_loop(self):
        """Background task to check connection health"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._cleanup_idle_connections()
                await self._ensure_minimum_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Health check error: {e}")
                
    async def _cleanup_idle_connections(self):
        """Remove idle connections from the pool"""
        async with self.lock:
            active_connections = []
            for conn in self.connections:
                if conn.is_active and not conn.is_idle(self.config.idle_timeout):
                    active_connections.append(conn)
                else:
                    conn.close()
                    
            self.connections = active_connections
            
    async def _ensure_minimum_connections(self):
        """Ensure we have at least 1 active connection"""
        async with self.lock:
            active_count = sum(1 for conn in self.connections if conn.is_active)
            if active_count == 0 and len(self.connections) < self.config.max_connections:
                conn = await self._create_connection()
                if conn:
                    self.connections.append(conn)
                    
    def get_pool_status(self) -> Dict[str, Any]:
        """Get current pool status"""
        active_connections = sum(1 for conn in self.connections if conn.is_active)
        idle_connections = sum(1 for conn in self.connections if conn.is_active and conn.is_idle(self.config.idle_timeout))
        
        return {
            "total_connections": len(self.connections),
            "active_connections": active_connections,
            "idle_connections": idle_connections,
            "max_connections": self.config.max_connections,
            "database_available": self.availability_checker.cached_state == DatabaseState.AVAILABLE
        }
