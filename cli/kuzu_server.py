#!/usr/bin/env python3
"""
Kuzu Neo4j-Compatible API Server

This is a Python implementation of an API server that can service Kuzu as if it's Neo4j,
based on the existing Node.js database proxy codebase.

Usage: python kuzu_server.py <path_to_kuzu_db>
"""

import os
import json
import asyncio
import sys
import logging
import traceback
import time
import threading
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from contextlib import asynccontextmanager
import signal
import psutil

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import kuzu

# Import our new pooling module
from kuzu_pool import KuzuConnectionPool, PoolConfig
from markdown_transformer import transform_markdown_images

def get_server_url() -> str:
    """
    Get the server URL using the same logic as KuzuServerManager.
    
    Returns:
        The constructed server URL with appropriate protocol and port
    """
    import os
    from pathlib import Path
    
    host = os.getenv("HOST", "localhost")
    port = 7001  # Default port
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    
    # Check for TLS certificates to determine SSL availability
    project_root = Path(__file__).parent.parent
    tls_cert = project_root / "tls.crt"
    tls_key = project_root / "tls.key"
    ssl_available = tls_cert.exists() and tls_key.exists()
    
    # Use SSL if explicitly enabled, or if certificates are available and SSL is not explicitly disabled
    protocol = "https" if (use_ssl or (ssl_available and os.getenv("USE_SSL", "").lower() != "false")) else "http"
    
    # If SSL is used and port is default 7001, use 8443 instead
    if protocol == "https" and port == 7001:
        port = 8443
    
    return f"{protocol}://{host}:{port}"

# Pydantic models for API requests
class MarkdownFileRequest(BaseModel):
    filename: str
    content: str

# Enhanced logging configuration
def setup_logging():
    """Setup enhanced logging with file and console handlers"""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler for detailed logs
    file_handler = logging.FileHandler('logs/kuzu_server.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    
    # File handler for errors only
    error_handler = logging.FileHandler('logs/kuzu_errors.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # Create specific logger for this module
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    return logger

# Setup logging
logger = setup_logging()

# Global crash tracking
class CrashTracker:
    """Tracks crashes and provides debugging information"""
    
    def __init__(self):
        self.crash_count = 0
        self.last_crash_time = None
        self.last_crash_query = None
        self.last_crash_traceback = None
        self.query_history = []
        self.max_query_history = 100
        self.lock = threading.Lock()
    
    def record_query(self, query: str, params: dict = None):
        """Record a query for debugging purposes"""
        with self.lock:
            query_info = {
                'timestamp': datetime.now().isoformat(),
                'query': query,
                'params': params,
                'thread_id': threading.current_thread().ident
            }
            self.query_history.append(query_info)
            
            # Keep only recent queries
            if len(self.query_history) > self.max_query_history:
                self.query_history.pop(0)
    
    def record_crash(self, error: Exception, query: str = None, params: dict = None):
        """Record a crash with full context"""
        with self.lock:
            self.crash_count += 1
            self.last_crash_time = datetime.now().isoformat()
            self.last_crash_query = query
            self.last_crash_traceback = traceback.format_exc()
            
            logger.error(f"CRASH #{self.crash_count} RECORDED:")
            logger.error(f"Time: {self.last_crash_time}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            logger.error(f"Error: {type(error).__name__}: {str(error)}")
            logger.error(f"Traceback:\n{self.last_crash_traceback}")
            
            # Log system information
            self._log_system_info()
    
    def _log_system_info(self):
        """Log system information for debugging"""
        try:
            process = psutil.Process()
            logger.error(f"Process ID: {process.pid}")
            logger.error(f"Memory Usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
            logger.error(f"CPU Usage: {process.cpu_percent()}%")
            logger.error(f"Thread Count: {process.num_threads()}")
            
            # Log system memory
            system_memory = psutil.virtual_memory()
            logger.error(f"System Memory: {system_memory.percent}% used ({system_memory.available / 1024 / 1024 / 1024:.2f} GB available)")
        except Exception as e:
            logger.error(f"Failed to log system info: {e}")
    
    def get_debug_info(self) -> dict:
        """Get debug information for troubleshooting"""
        with self.lock:
            return {
                'crash_count': self.crash_count,
                'last_crash_time': self.last_crash_time,
                'last_crash_query': self.last_crash_query,
                'recent_queries': self.query_history[-10:] if self.query_history else [],
                'system_info': self._get_current_system_info()
            }
    
    def _get_current_system_info(self) -> dict:
        """Get current system information"""
        try:
            process = psutil.Process()
            return {
                'pid': process.pid,
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'cpu_percent': process.cpu_percent(),
                'thread_count': process.num_threads(),
                'system_memory_percent': psutil.virtual_memory().percent
            }
        except Exception as e:
            return {'error': str(e)}

# Global crash tracker instance
crash_tracker = CrashTracker()

# Constants
MAX_QUERY_RESULTS = 20000
QUERY_TIMEOUT = 60000
KUZU_VERSION = "0.11.2"
KUZU_STORAGE_VERSION = "0.11.2"

# Data Models
class QueryRequest(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = {}
    timeout: Optional[int] = QUERY_TIMEOUT

class QueryResponse(BaseModel):
    status: int
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@dataclass
class Node:
    id: str
    labels: List[str]
    properties: Dict[str, Any]

@dataclass
class Relationship:
    id: str
    startNodeId: str
    endNodeId: str
    type: str
    properties: Dict[str, Any]

@dataclass
class QueryResult:
    data: Union[Dict[str, Any], List[List[Any]]]
    type: str  # "GRAPH", "TABLE", or "SCHEMA"
    summary: Dict[str, Any]

class KuzuQueryProcessor:
    """Processes Kuzu queries and converts results to Neo4j-compatible format"""
    
    def __init__(self, db_path: str, pool_config: PoolConfig = None, vault_path: str = None):
        self.db_path = db_path
        self.vault_path = vault_path
        self.pool_config = pool_config or PoolConfig()
        
        # Extract vault path from db_path if not provided
        if vault_path is None:
            # db_path format: vault_path/.kineviz_graph/database/knowledge_graph.kz
            db_path_obj = Path(db_path)
            if db_path_obj.name == "knowledge_graph.kz" and db_path_obj.parent.name == "database":
                # Go up two levels: database -> .kineviz_graph -> vault
                self.vault_path = str(db_path_obj.parent.parent.parent)
            else:
                self.vault_path = None
        else:
            self.vault_path = vault_path
            
        self.connection_pool = None
        self.query_count = 0
        self.error_count = 0
        self.start_time = time.time()
    
    async def initialize_connection(self):
        """Initialize Kuzu database connection pool"""
        try:
            logger.info(f"Initializing Kuzu connection pool to: {self.db_path}")
            
            # Create database directory if it doesn't exist
            db_dir = os.path.dirname(self.db_path)
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"Created database directory: {db_dir}")
            
            # Create connection pool
            self.connection_pool = KuzuConnectionPool(self.db_path, self.pool_config)
            
            # Start the pool (this will wait for database to be available)
            success = await self.connection_pool.start()
            if not success:
                raise Exception("Failed to start connection pool")
            
            logger.info(f"Successfully initialized Kuzu connection pool at: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kuzu connection pool: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            crash_tracker.record_crash(e, "INIT_CONNECTION")
            raise e
    
    async def cleanup(self):
        """Cleanup connection pool"""
        if self.connection_pool:
            await self.connection_pool.stop()
    
    def validate_query(self, query: str) -> tuple[bool, str]:
        """Validate query for potential issues"""
        if not query or not query.strip():
            return False, "Query is empty"
        
        query_lower = query.lower().strip()
        
        # Check query length FIRST - this is critical to prevent server freeze
        if len(query) > 10000:
            return False, f"Query is too long ({len(query)} characters, max 10000 characters)"
        
        # Check for potentially dangerous patterns
        dangerous_patterns = [
            "drop database",
            "delete database",
            "shutdown",
            "kill",
            "terminate"
        ]
        
        for pattern in dangerous_patterns:
            if pattern in query_lower:
                return False, f"Query contains potentially dangerous pattern: {pattern}"
        
        # Check for problematic patterns that can cause Kuzu to hang
        # (We'll warn but not reject these, since they might be legitimate queries)
        import re
        problematic_patterns = [
            # Property filtering on non-existent properties (known to cause hangs)
            r"where\s+\w+\.\w+\s*=\s*['\"][^'\"]*['\"]",
            # Complex WHERE clauses that might cause issues
            r"where\s+.*\s+and\s+.*\s+and\s+.*\s+and",
            # Nested subqueries that might cause problems
            r"where\s+.*\s+in\s*\(",
        ]
        
        for pattern in problematic_patterns:
            if re.search(pattern, query_lower):
                logger.warning(f"Query contains potentially problematic pattern: {pattern}")
                # Don't reject, just warn - let it through but with timeout protection
        
        # Check for high SKIP values that can cause freezes
        skip_match = re.search(r'skip\s+(\d+)', query_lower)
        if skip_match:
            skip_value = int(skip_match.group(1))
            if skip_value > 10000:  # Reject queries with SKIP > 10000
                return False, f"SKIP value too high ({skip_value}), max allowed is 10000"
            elif skip_value > 5000:  # Warn for high SKIP values
                logger.warning(f"High SKIP value detected: {skip_value}, may cause performance issues")
        
        return True, "Query is valid"
    
    def preprocess_query(self, query: str) -> str | list:
        """Preprocess Kuzu query to handle special cases and transformations"""
        try:
            logger.debug(f"Preprocessing query: {query[:100]}...")
            
            query_lower = query.lower().strip()
            
            # Handle schema requests
            if "call schema" in query_lower:
                logger.debug("Detected schema request")
                return "CALL show_tables() RETURN *"
            
            # Handle test data creation
            if "call test" in query_lower:
                logger.debug("Detected test data request")
                return self._create_test_data_queries()
            
            # Handle database listing
            if any(cmd in query_lower for cmd in ["show databases", "call list", "call dbs", "show tables"]):
                logger.debug("Detected database listing request")
                return "CALL show_tables() RETURN *"
            
            # Handle null label issue - replace :null with :Unknown or remove label
            if ":null" in query_lower:
                logger.warning("Detected null label in query, replacing with :Unknown")
                query = query.replace(":null", ":Unknown")
                query = query.replace(":NULL", ":Unknown")
            
            # Add automatic LIMIT if missing
            if "return" in query_lower and "limit" not in query_lower:
                query = f"{query.rstrip(';')} LIMIT {MAX_QUERY_RESULTS}"
                logger.debug(f"Added automatic LIMIT {MAX_QUERY_RESULTS}")
            
            logger.debug(f"Query preprocessing completed")
            return query
            
        except Exception as e:
            logger.error(f"Error during query preprocessing: {e}")
            crash_tracker.record_crash(e, query, "PREPROCESS")
            raise e

    def _create_test_data_queries(self) -> list:
        """Return a list of queries to create test data, each as a separate statement"""
        return [
            "CREATE NODE TABLE Movie (name STRING, PRIMARY KEY(name));",
            "CREATE NODE TABLE Person (name STRING, birthDate STRING, PRIMARY KEY(name));",
            "CREATE REL TABLE ActedIn (FROM Person TO Movie);",
            "CREATE (:Person {name: 'Al Pacino', birthDate: '1940-04-25'});",
            "CREATE (:Person {name: 'Robert De Nero', birthDate: '1943-08-17'});",
            "CREATE (:Movie {name: 'The Godfather: Part II'});",
            "MATCH (p:Person), (m:Movie) WHERE p.name = 'Al Pacino' AND m.name = 'The Godfather: Part II' CREATE (p)-[:ActedIn]->(m);",
            "MATCH (p:Person), (m:Movie) WHERE p.name = 'Robert De Nero' AND m.name = 'The Godfather: Part II' CREATE (p)-[:ActedIn]->(m);",
            "MATCH (u)-[r]->(m) RETURN u, r, m LIMIT 10;"
        ]
    
    def create_node(self, item: Any) -> Node:
        """Create a Node object from Kuzu result"""
        try:
            # Extract properties, excluding internal fields
            props = {}
            for key, value in item.items():
                if key not in ["_id", "_label", "_src", "_dst"] and value is not None:
                    props[key] = value
            
            # Create ID in Kuzu format
            node_id = f"{item['_id']['table']}:{item['_id']['offset']}"
            
            return Node(
                id=node_id,
                labels=[item['_label']],
                properties=props
            )
        except Exception as e:
            logger.error(f"Error creating node from item: {e}")
            logger.error(f"Item data: {item}")
            crash_tracker.record_crash(e, "CREATE_NODE", {"item": str(item)})
            raise e
    
    def create_relationship(self, item: Any) -> Relationship:
        """Create a Relationship object from Kuzu result"""
        try:
            # Extract properties, excluding internal fields
            props = {}
            for key, value in item.items():
                if key not in ["_id", "_label", "_src", "_dst"] and value is not None:
                    props[key] = value
            
            # Create IDs in Kuzu format
            rel_id = f"{item['_id']['table']}:{item['_id']['offset']}"
            start_id = f"{item['_src']['table']}:{item['_src']['offset']}"
            end_id = f"{item['_dst']['table']}:{item['_dst']['offset']}"
            
            return Relationship(
                id=rel_id,
                startNodeId=start_id,
                endNodeId=end_id,
                type=item['_label'],
                properties=props
            )
        except Exception as e:
            logger.error(f"Error creating relationship from item: {e}")
            logger.error(f"Item data: {item}")
            crash_tracker.record_crash(e, "CREATE_RELATIONSHIP", {"item": str(item)})
            raise e
    
    async def execute_query(self, query: str | list) -> List[Dict[str, Any]]:
        """Execute a query against the Kuzu database using connection pool"""
        start_time = time.time()
        self.query_count += 1
        
        try:
            # Print query execution prominently
            print(f"\n{'='*60}")
            print(f"⚡ EXECUTING QUERY #{self.query_count}:")
            if isinstance(query, list):
                print(f"Multiple queries ({len(query)} total)")
                for i, q in enumerate(query):
                    print(f"  {i+1}. {q}")
            else:
                print(f"Query: {query}")
            print(f"{'='*60}\n")
            
            logger.debug(f"Executing query #{self.query_count}")
            logger.debug(f"Query: {query[:200]}...")
            
            if isinstance(query, list):
                # Handle multiple queries (e.g., for test data creation)
                logger.debug(f"Executing {len(query)} queries")
                results = []
                for i, q in enumerate(query):
                    logger.debug(f"Executing sub-query {i+1}/{len(query)}: {q[:100]}...")
                    result = await self.connection_pool.execute_query_with_retry(q)
                    if result.get("status") == "success":
                        results.extend(result.get("data", []))
                    else:
                        logger.error(f"Sub-query {i+1} failed: {result.get('message')}")
                        raise Exception(f"Sub-query {i+1} failed: {result.get('message')}")
                    logger.debug(f"Sub-query {i+1} returned {len(result.get('data', []))} rows")
                
                execution_time = time.time() - start_time
                print(f"✅ QUERY #{self.query_count} COMPLETED in {execution_time:.3f}s - {len(results)} rows returned\n")
                logger.info(f"Multiple query execution completed in {execution_time:.3f}s, total rows: {len(results)}")
                return results
            else:
                # Handle single query using connection pool with retry
                result = await self.connection_pool.execute_query_with_retry(query)
                
                if result.get("status") == "success":
                    rows = result.get("data", [])
                    execution_time = time.time() - start_time
                    print(f"✅ QUERY #{self.query_count} COMPLETED in {execution_time:.3f}s - {len(rows)} rows returned\n")
                    logger.info(f"Single query execution completed in {execution_time:.3f}s, returned {len(rows)} rows")
                    return rows
                else:
                    # Query failed, raise exception with error details
                    error_msg = result.get("message", "Unknown error")
                    raise Exception(f"Query execution failed: {error_msg}")
                
        except Exception as e:
            self.error_count += 1
            execution_time = time.time() - start_time
            logger.error(f"Query execution error after {execution_time:.3f}s: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            crash_tracker.record_crash(e, str(query))
            raise e
    
    async def get_schema_info(self) -> Dict[str, Any]:
        """Get schema information in Node.js format"""
        try:
            logger.debug("Getting schema information")
            start_time = time.time()
            
            # Get all tables using connection pool
            tables_result = await self.connection_pool.execute_query_with_retry("CALL show_tables() RETURN *")
            if tables_result.get("status") != "success":
                raise Exception(f"Failed to get tables: {tables_result.get('message')}")
            
            tables = tables_result.get("data", [])
            
            logger.debug(f"Found {len(tables)} tables")
            
            # Initialize schema structure matching Node.js format
            schema = {
                "categories": {},
                "relationships": {}
            }
            
            # First pass: create basic structure
            for table in tables:
                table_name = table.get("name", "")
                table_type = table.get("type", "")
                
                if table_type == "NODE":
                    schema["categories"][table_name] = {
                        "name": table_name,
                        "props": {},
                        "keys": {}
                    }
                elif table_type == "REL":
                    schema["relationships"][table_name] = {
                        "name": table_name,
                        "props": {},
                        "keys": {}
                    }
            
            logger.debug(f"Schema structure created: {len(schema['categories'])} categories, {len(schema['relationships'])} relationships")
            
            # Second pass: get relationship endpoints
            if schema["relationships"]:
                rel_cyphers = []
                for rel_name in schema["relationships"].keys():
                    rel_cyphers.append(f'CALL SHOW_CONNECTION("{rel_name}") RETURN `source table name` as source, `destination table name` as target, "{rel_name}" as type')
                
                if rel_cyphers:
                    rel_query = " UNION ".join(rel_cyphers)
                    logger.debug(f"Executing relationship connection query: {rel_query[:200]}...")
                    rel_result = await self.connection_pool.execute_query_with_retry(rel_query)
                    if rel_result.get("status") == "success":
                        for rel_data in rel_result.get("data", []):
                            rel_type = rel_data.get("type", "")
                            if rel_type in schema["relationships"]:
                                schema["relationships"][rel_type]["startCategory"] = rel_data.get("source", "")
                                schema["relationships"][rel_type]["endCategory"] = rel_data.get("target", "")
            
            # Third pass: get table properties and keys
            if schema["categories"] or schema["relationships"]:
                # Build UNION query for all table info
                table_queries = []
                
                # Node table queries
                for node_name in schema["categories"].keys():
                    table_queries.append(f'''
CALL TABLE_INFO("{node_name}")
YIELD `property id` as id, name as name, type as type, `default expression` as defaultValue, `primary key` as isKey
RETURN name, type, isKey, "{node_name}" as tableName
LIMIT 2000''')
                
                # Relationship table queries
                for rel_name in schema["relationships"].keys():
                    table_queries.append(f'''
CALL TABLE_INFO("{rel_name}")
YIELD `property id` as id, name as name, type as type, `default expression` as defaultValue, storage_direction as direction
RETURN name, type, false as isKey, "{rel_name}" as tableName
LIMIT 2000''')
                
                if table_queries:
                    table_query = "\nUNION\n".join(table_queries)
                    logger.debug(f"Executing table info query: {table_query[:200]}...")
                    table_result = await self.connection_pool.execute_query_with_retry(table_query)
                    if table_result.get("status") == "success":
                        for table_data in table_result.get("data", []):
                            table_name = table_data.get("tableName", "")
                            prop_name = table_data.get("name", "")
                            prop_type = table_data.get("type", "")
                            is_key = table_data.get("isKey", False)
                            
                            # Find the table in either categories or relationships
                            if table_name in schema["categories"]:
                                category = schema["categories"][table_name]
                                category["props"][prop_name] = prop_type
                                if is_key:
                                    category["keys"][prop_name] = prop_type
                            elif table_name in schema["relationships"]:
                                relationship = schema["relationships"][table_name]
                                relationship["props"][prop_name] = prop_type
                                if is_key:
                                    relationship["keys"][prop_name] = prop_type
            
            # Fourth pass: convert to Node.js format (separate props from propsTypes)
            for cat_name in schema["categories"]:
                category = schema["categories"][cat_name]
                category["propsTypes"] = category["props"].copy()
                category["keysTypes"] = category["keys"].copy()
                category["props"] = list(category["props"].keys())
                category["keys"] = list(category["keys"].keys())
            
            for rel_name in schema["relationships"]:
                relationship = schema["relationships"][rel_name]
                relationship["propsTypes"] = relationship["props"].copy()
                relationship["keysTypes"] = relationship["keys"].copy()
                relationship["props"] = list(relationship["props"].keys())
                relationship["keys"] = list(relationship["keys"].keys())
            
            # Wrap in database name like Node.js does
            schema_data = {"testdb": schema}
            
            execution_time = time.time() - start_time
            logger.info(f"Schema info retrieved in {execution_time:.3f}s")
            return schema_data
            
        except Exception as e:
            logger.error(f"Error getting schema info: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            crash_tracker.record_crash(e, "GET_SCHEMA_INFO")
            # Return empty schema in Node.js format
            return {
                "testdb": {
                    "categories": {},
                    "relationships": {}
                }
            }
    
    async def convert_cypher_result_to_graph(self, results: List[Dict[str, Any]]) -> QueryResult:
        """Convert Kuzu query results to Neo4j-compatible graph format"""
        try:
            logger.debug(f"Converting {len(results)} results to graph format")
            start_time = time.time()
            
            nodes = []
            relationships = []
            tables = []
            
            for i, row in enumerate(results):
                try:
                    is_table = False
                    has_nodes_or_rels = False
                    
                    for key, item in row.items():
                        # Check if this is a relationship result (has _src and _dst)
                        if isinstance(item, dict) and '_src' in item and '_dst' in item and '_label' in item:
                            has_nodes_or_rels = True
                            relationships.append(self.create_relationship(item))
                        # Check if this is a node result (has _id and _label but no _src/_dst)
                        elif isinstance(item, dict) and '_id' in item and '_label' in item and '_src' not in item and '_dst' not in item:
                            has_nodes_or_rels = True
                            nodes.append(self.create_node(item))
                        # Handle different result types
                        elif hasattr(item, '_nodes'):
                            # Handle node collections
                            has_nodes_or_rels = True
                            for node in item._nodes:
                                nodes.append(self.create_node(node))
                        elif hasattr(item, '_rels'):
                            # Handle relationship collections
                            has_nodes_or_rels = True
                            for rel in item._rels:
                                relationships.append(self.create_relationship(rel))
                        elif hasattr(item, '_src') and hasattr(item, '_dst'):
                            # Handle single relationship
                            has_nodes_or_rels = True
                            relationships.append(self.create_relationship(item))
                        elif hasattr(item, '_label') and hasattr(item, '_id'):
                            # Handle single node
                            has_nodes_or_rels = True
                            nodes.append(self.create_node(item))
                        else:
                            is_table = True
                    
                    if is_table and not has_nodes_or_rels:
                        tables.append(row)
                        
                except Exception as e:
                    logger.error(f"Error processing row {i}: {e}")
                    logger.error(f"Row data: {row}")
                    # Continue processing other rows instead of failing completely
                    continue
            
            # Determine result type and format
            if nodes or relationships:
                # Return as graph if we have nodes or relationships
                result = QueryResult(
                    data={
                        "nodes": [self._node_to_dict(node) for node in nodes],
                        "relationships": [self._relationship_to_dict(rel) for rel in relationships]
                    },
                    type="GRAPH",
                    summary=self._get_kuzu_summary()
                )
            elif tables:
                # Return as table only if we have no nodes/relationships
                result = QueryResult(
                    data=self._convert_to_table_format(tables),
                    type="TABLE",
                    summary=self._get_kuzu_summary()
                )
            else:
                # Empty result
                result = QueryResult(
                    data={"nodes": [], "relationships": []},
                    type="GRAPH",
                    summary=self._get_kuzu_summary()
                )
            
            execution_time = time.time() - start_time
            logger.debug(f"Result conversion completed in {execution_time:.3f}s: {len(nodes)} nodes, {len(relationships)} relationships, {len(tables)} table rows")
            return result
            
        except Exception as e:
            logger.error(f"Error converting results to graph: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            crash_tracker.record_crash(e, "CONVERT_TO_GRAPH", {"results_count": len(results)})
            raise e
    
    def _convert_to_table_format(self, tables: List[Dict[str, Any]]) -> List[List[Any]]:
        """Convert table data to 2D array format"""
        if not tables:
            return []
        
        # Get column names from first row
        columns = list(tables[0].keys())
        result = [columns]
        
        # Add data rows
        for row in tables:
            result.append([row.get(col) for col in columns])
        
        return result
    
    def _node_to_dict(self, node: Node) -> Dict[str, Any]:
        """Convert Node to dictionary"""
        node_dict = {
            "id": node.id,
            "labels": node.labels,
            "properties": node.properties
        }
        
        # Auto-transform markdown content in Note nodes if vault_path is available
        if self.vault_path and 'Note' in node.labels and 'content' in node.properties:
            try:
                # Get server URL using the same logic as KuzuServerManager
                server_url = get_server_url()
                
                # Transform the markdown content
                node_dict["properties"]["content"] = transform_markdown_images(
                    node.properties["content"],
                    server_url=server_url,
                    vault_path=self.vault_path,
                    current_file_path=node.properties.get("url")
                )
            except Exception as e:
                logger.warning(f"Failed to transform markdown content for node {node.id}: {e}")
        
        return node_dict
    
    def _relationship_to_dict(self, rel: Relationship) -> Dict[str, Any]:
        """Convert Relationship to dictionary"""
        return {
            "id": rel.id,
            "startNodeId": rel.startNodeId,
            "endNodeId": rel.endNodeId,
            "type": rel.type,
            "properties": rel.properties
        }
    
    def _get_kuzu_summary(self) -> Dict[str, Any]:
        """Get Kuzu summary information"""
        # Create summary information
        summary = {
            "version": KUZU_VERSION,
            "storageVersion": KUZU_STORAGE_VERSION
        }
        return summary
    
    def get_stats(self) -> dict:
        """Get query processor statistics"""
        uptime = time.time() - self.start_time
        return {
            'uptime_seconds': uptime,
            'uptime_formatted': f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s",
            'total_queries': self.query_count,
            'error_count': self.error_count,
            'success_rate': ((self.query_count - self.error_count) / self.query_count * 100) if self.query_count > 0 else 0,
            'database_path': self.db_path
        }

def print_usage():
    """Print usage information"""
    print("""
Kuzu Neo4j-Compatible API Server

Usage: python kuzu_server.py <path_to_kuzu_db> [options]

Arguments:
  path_to_kuzu_db    Path to the Kuzu database directory

Options:
  --port PORT        Port to run the server on (default: 2899)
  --host HOST        Host to bind to (default: 0.0.0.0)
  --ssl-cert PATH    Path to SSL certificate file (enables HTTPS)
  --ssl-key PATH     Path to SSL private key file (required with --ssl-cert)
  --ssl-password     Password for SSL private key (if encrypted)
  --debug            Enable debug mode with verbose logging

Examples:
  # HTTP server
  python kuzu_server.py /data/kuzu/my_database
  python kuzu_server.py ./my_kuzu_db --port 3000

  # HTTPS server with SSL certificates
  python kuzu_server.py ./my_kuzu_db --ssl-cert cert.pem --ssl-key key.pem
  python kuzu_server.py ./my_kuzu_db --ssl-cert cert.pem --ssl-key key.pem --port 8443

  # HTTPS with encrypted private key
  python kuzu_server.py ./my_kuzu_db --ssl-cert cert.pem --ssl-key key.pem --ssl-password mypassword

  # Debug mode
  python kuzu_server.py ./my_kuzu_db --debug
""")

def parse_arguments():
    """Parse command line arguments"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Kuzu Neo4j-Compatible API Server")
    parser.add_argument("db_path", help="Path to the Kuzu database directory")
    parser.add_argument("--vault-path", help="Path to Obsidian vault (enables image serving and /save-markdown)")
    parser.add_argument("--port", type=int, default=7001, help="Port to run the server on (default: 7001)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--ssl-cert", help="Path to SSL certificate file (enables HTTPS)")
    parser.add_argument("--ssl-key", help="Path to SSL private key file (required with --ssl-cert)")
    parser.add_argument("--ssl-password", help="Password for SSL private key (if encrypted)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with verbose logging")
    
    return parser.parse_args()

def validate_ssl_config(ssl_cert, ssl_key, ssl_password):
    """Validate SSL configuration"""
    if ssl_cert and not ssl_key:
        raise ValueError("--ssl-key is required when --ssl-cert is provided")
    
    if ssl_key and not ssl_cert:
        raise ValueError("--ssl-cert is required when --ssl-key is provided")
    
    if ssl_cert and not os.path.exists(ssl_cert):
        raise FileNotFoundError(f"SSL certificate file not found: {ssl_cert}")
    
    if ssl_key and not os.path.exists(ssl_key):
        raise FileNotFoundError(f"SSL private key file not found: {ssl_key}")
    
    return ssl_cert and ssl_key

def create_app(query_processor: KuzuQueryProcessor) -> FastAPI:
    """Create and configure the FastAPI application"""
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Lifespan context manager for FastAPI app"""
        # Startup - initialize query processor
        if query_processor is None:
            raise RuntimeError("Query processor not initialized.")
        
        try:
            await query_processor.initialize_connection()
            print(f"Connected to Kuzu database at: {query_processor.db_path}")
            logger.info("FastAPI application started successfully")
        except Exception as e:
            print(f"Failed to connect to database: {e}")
            print(f"Check the logs at logs/kuzu_server.log for more details")
            raise e
        
        yield
        
        # Shutdown - cleanup connection pool
        if query_processor:
            await query_processor.cleanup()
        logger.info("FastAPI application shutting down")
    
    app = FastAPI(title="Kuzu Neo4j-Compatible API", version="1.0.0", lifespan=lifespan)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Debug endpoint to get crash information
    @app.get("/debug/crashes")
    async def get_crash_info():
        """Get crash and debugging information"""
        try:
            debug_info = crash_tracker.get_debug_info()
            stats = query_processor.get_stats()
            return {
                "crash_info": debug_info,
                "processor_stats": stats,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting debug info: {e}")
            return {"error": str(e)}
    
    # Image serving endpoint
    @app.get("/images/{image_path:path}")
    async def serve_image(image_path: str):
        """Serve images from the vault directory"""
        try:
            if not query_processor.vault_path:
                raise HTTPException(
                    status_code=503,
                    detail="Vault path not configured. Server must be started with --vault-path argument."
                )
            
            # Construct full path to image
            vault_path = Path(query_processor.vault_path)
            full_image_path = vault_path / image_path
            
            # Security check: ensure the resolved path is within the vault directory
            try:
                full_image_path = full_image_path.resolve()
                vault_path = vault_path.resolve()
                if not str(full_image_path).startswith(str(vault_path)):
                    raise HTTPException(status_code=403, detail="Access denied: path outside vault")
            except Exception as e:
                logger.error(f"Error resolving path {image_path}: {e}")
                raise HTTPException(status_code=400, detail="Invalid path")
            
            # Check if file exists
            if not full_image_path.exists() or not full_image_path.is_file():
                raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")
            
            # Check if it's an image file (basic check by extension)
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico'}
            if full_image_path.suffix.lower() not in image_extensions:
                raise HTTPException(status_code=400, detail="Not an image file")
            
            logger.debug(f"Serving image: {full_image_path}")
            return FileResponse(full_image_path)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error serving image {image_path}: {e}")
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        try:
            # Test database connection using pool
            test_result = await query_processor.connection_pool.execute_query_with_retry("CALL show_tables() RETURN *")
            if test_result.get("status") == "success":
                return {
                    "status": "healthy",
                    "database": "connected",
                    "pool_status": query_processor.connection_pool.get_pool_status(),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "unhealthy",
                    "database": "disconnected",
                    "error": test_result.get("message", "Unknown error"),
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    # Save markdown file endpoint
    @app.post("/save-markdown")
    async def save_markdown_file(request: MarkdownFileRequest):
        """Save a markdown file to the Obsidian vault"""
        try:
            if not query_processor.vault_path:
                raise HTTPException(
                    status_code=500, 
                    detail="Vault path could not be determined from database path. Expected format: vault_path/.kineviz_graph/database/knowledge_graph.kz"
                )
            
            # Create GraphXRNotes folder if it doesn't exist
            vault_path = Path(query_processor.vault_path)
            graphxr_notes_dir = vault_path / "GraphXRNotes"
            graphxr_notes_dir.mkdir(exist_ok=True)
            
            # Ensure filename has .md extension
            filename = request.filename
            if not filename.endswith('.md'):
                filename += '.md'
            
            # Create the file path
            file_path = graphxr_notes_dir / filename
            
            # Write the content to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(request.content)
            
            logger.info(f"Saved markdown file: {file_path}")
            
            return {
                "status": "success",
                "message": f"File saved successfully as {filename}",
                "file_path": str(file_path),
                "vault_path": str(vault_path),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error saving markdown file: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save markdown file: {str(e)}"
            )
    # Endpoint to transform markdown content
    @app.post("/transform_markdown")
    async def transform_markdown_endpoint(request: Request):
        """Transform markdown content to update image links"""
        try:
            body = await request.json()
            content = body.get("content", "")
            # Use the same server URL logic as KuzuServerManager for consistency
            if "server_url" in body:
                server_url = body.get("server_url")
            else:
                server_url = get_server_url()
            vault_path = body.get("vault_path", query_processor.vault_path)
            current_file_path = body.get("current_file_path")
            
            transformed = transform_markdown_images(
                content,
                server_url=server_url,
                vault_path=vault_path,
                current_file_path=current_file_path
            )
            
            return {
                "original": content,
                "transformed": transformed,
                "status": 0,
                "message": "Successful"
            }
        except Exception as e:
            logger.error(f"Error transforming markdown: {e}")
            return {
                "status": 1,
                "message": str(e)
            }
    
    # Main kuzudb route - matches Node.js POST /kuzudb/:name
    @app.post("/kuzudb/{name}")
    async def kuzudb_query(name: str, request: Request):
        """Main kuzudb query endpoint - matches Node.js implementation exactly"""
        request_start_time = time.time()
        request_id = f"{int(request_start_time * 1000)}"
        
        # Log request start immediately with more details
        from datetime import datetime
        import psutil
        import os
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent()
        
        print(f"\n🚀 REQUEST START [{timestamp}] - Request {request_id} - Database: {name}")
        print(f"   📊 Server Stats: Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")
        logger.info(f"[{timestamp}] REQUEST START - Request {request_id} - Database: {name} - Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")
        
        try:
            # Parse request body
            body = await request.json()
            query = body.get("query") or body.get("sql") or body.get("gql") or body.get("cypher") or body.get("command")
            params = body.get("params", {})
            
            if not query:
                logger.warning(f"Request {request_id}: Missing query parameter")
                return {
                    "data": None,
                    "status": 1,
                    "message": "query parameter is required."
                }
            
            # Record query for debugging
            crash_tracker.record_query(query, params)
            
            # Print query prominently to console with timestamp (truncate if too long)
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"\n{'='*80}")
            print(f"🔍 QUERY RECEIVED [{timestamp}] (Request {request_id}):")
            print(f"Database: {name}")
            if len(query) > 200:
                print(f"Query: {query[:200]}... (truncated, full length: {len(query)} chars)")
            else:
                print(f"Query: {query}")
            if params:
                print(f"Params: {params}")
            print(f"{'='*80}\n")
            
            # Also log to file with timestamp
            logger.info(f"[{timestamp}] QUERY RECEIVED - Request {request_id} - Database: {name} - Query: {query[:100]}...")
            
            logger.info(f"Request {request_id}: kuzu: {query[:100]}..., database: {name}")
            logger.debug(f"Request {request_id}: Full query: {query}")
            logger.debug(f"Request {request_id}: Params: {params}")
            
            # Validate query
            is_valid, validation_message = query_processor.validate_query(query)
            if not is_valid:
                logger.warning(f"Request {request_id}: Query validation failed: {validation_message}")
                logger.warning(f"Request {request_id}: Query length: {len(query)} characters")
                logger.warning(f"Request {request_id}: Query preview: {query[:200]}...")
                return {
                    "data": None,
                    "status": 1,
                    "message": f"Query validation failed: {validation_message}"
                }
            
            # Check if this is a schema query
            if query.strip().upper() in ["CALL SCHEMA", "CALL SCHEMA()"]:
                logger.debug(f"Request {request_id}: Processing schema request")
                # Return schema in Node.js format
                schema_data = await query_processor.get_schema_info()
                request_time = time.time() - request_start_time
                logger.info(f"Request {request_id}: Schema request completed in {request_time:.3f}s")
                return {
                    "data": schema_data,
                    "status": 0,
                    "message": "Successful"
                }
            
            # Preprocess the query
            logger.debug(f"Request {request_id}: Preprocessing query")
            processed_query = query_processor.preprocess_query(query)
            
            # Execute the query
            logger.debug(f"Request {request_id}: Executing query")
            results = await query_processor.execute_query(processed_query)
            
            # Convert results to Node.js-compatible format
            logger.debug(f"Request {request_id}: Converting results")
            query_result = await query_processor.convert_cypher_result_to_graph(results)
            
            request_time = time.time() - request_start_time
            completion_timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            print(f"✅ QUERY COMPLETED [{completion_timestamp}] - Request {request_id} - Time: {request_time:.3f}s")
            print(f"   📊 Server Stats: Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")
            logger.info(f"[{completion_timestamp}] QUERY COMPLETED - Request {request_id} - Time: {request_time:.3f}s - Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")
            logger.info(f"Request {request_id}: Query completed successfully in {request_time:.3f}s")
            
            return {
                "data": {
                    "data": query_result.data,
                    "type": query_result.type,
                    "summary": query_result.summary
                },
                "status": 0,
                "message": "Successful"
            }
        
        except Exception as e:
            request_time = time.time() - request_start_time
            error_timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            print(f"❌ QUERY ERROR [{error_timestamp}] - Request {request_id} - Time: {request_time:.3f}s")
            print(f"   📊 Server Stats: Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")
            print(f"   🚨 Error: {e}")
            
            logger.error(f"[{error_timestamp}] QUERY ERROR - Request {request_id} - Time: {request_time:.3f}s - Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%")
            logger.error(f"Request {request_id}: Error executing query after {request_time:.3f}s: {e}")
            logger.error(f"Request {request_id}: Query: {query if 'query' in locals() else 'UNKNOWN'}")
            logger.error(f"Request {request_id}: Traceback:\n{traceback.format_exc()}")
            
            # Record crash for debugging
            crash_tracker.record_crash(e, query if 'query' in locals() else 'UNKNOWN', params if 'params' in locals() else {})
            
            return {
                "data": None,
                "status": 1,
                "message": str(e)
            }
    
    return app

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def main():
    """Main function to run the server"""
    try:
        args = parse_arguments()
    except SystemExit:
        print_usage()
        sys.exit(1)
    
    # Setup signal handlers
    setup_signal_handlers()
    
    db_path = args.db_path
    
    # Validate database path
    if not os.path.exists(db_path):
        print(f"Creating database directory: {db_path}")
        os.makedirs(db_path, exist_ok=True)
    
    # Validate SSL configuration
    try:
        use_ssl = validate_ssl_config(args.ssl_cert, args.ssl_key, args.ssl_password)
    except (ValueError, FileNotFoundError) as e:
        print(f"SSL configuration error: {e}")
        sys.exit(1)
    
    # Initialize query processor with custom pool config
    pool_config = PoolConfig(
        max_connections=5,
        max_retries=3,
        retry_delay=10,
        idle_timeout=300,
        health_check_interval=60
    )
    query_processor = KuzuQueryProcessor(db_path, pool_config, vault_path=args.vault_path)
    
    # Create FastAPI app with the query processor
    app = create_app(query_processor)
    
    # Determine protocol and port
    protocol = "https" if use_ssl else "http"
    default_port = 8443 if use_ssl else 7001
    port = args.port if args.port != 7001 else default_port
    
    # Run the server
    print(f"Starting Kuzu Neo4j-Compatible API Server on {protocol}://{args.host}:{port}")
    print(f"Database: {db_path}")
    if args.vault_path:
        print(f"Vault Path: {args.vault_path}")
        print(f"Image serving enabled at: {protocol}://{args.host}:{port}/images/{{path}}")
    if use_ssl:
        print(f"SSL Certificate: {args.ssl_cert}")
        print(f"SSL Private Key: {args.ssl_key}")
    print("Debug endpoints available at:")
    print(f"  {protocol}://{args.host}:{port}/debug/crashes")
    print(f"  {protocol}://{args.host}:{port}/health")
    if args.vault_path:
        print(f"  {protocol}://{args.host}:{port}/save-markdown")
    print("Press Ctrl+C to stop the server")
    
    # Configure uvicorn with SSL if enabled
    uvicorn_config = {
        "app": app,
        "host": args.host,
        "port": port,
        "reload": False,  # Disable reload for production
        "log_level": "debug" if args.debug else "info"
    }
    
    if use_ssl:
        # Read SSL certificate and key files
        try:
            with open(args.ssl_cert, 'rb') as f:
                ssl_certfile = f.read()
            
            with open(args.ssl_key, 'rb') as f:
                ssl_keyfile = f.read()
            
            # Configure SSL context
            import ssl
            ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            ssl_context.load_cert_chain(
                certfile=args.ssl_cert,
                keyfile=args.ssl_key,
                password=args.ssl_password
            )
            
            uvicorn_config["ssl_certfile"] = args.ssl_cert
            uvicorn_config["ssl_keyfile"] = args.ssl_key
            if args.ssl_password:
                uvicorn_config["ssl_keyfile_password"] = args.ssl_password
            
        except Exception as e:
            print(f"Failed to load SSL certificates: {e}")
            sys.exit(1)
    
    try:
        uvicorn.run(**uvicorn_config)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server crashed: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        crash_tracker.record_crash(e, "SERVER_CRASH")
        sys.exit(1)

if __name__ == "__main__":
    main() 