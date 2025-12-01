#!/usr/bin/env python3
"""
LLM Client with Load Balancing and Failover
Supports both OpenAI (cloud) and Ollama (local) providers with automatic failover.
"""

import asyncio
import aiohttp
import json
import time
import random
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import openai
from dotenv import load_dotenv
import os
from config_loader import get_config_loader

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    CLOUD = "cloud"
    OLLAMA = "ollama"

class LoadBalanceStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    FASTEST_RESPONSE = "fastest_response"

@dataclass
class OllamaServer:
    """Represents an Ollama server with health status"""
    url: str
    is_healthy: bool = True
    last_health_check: float = 0
    response_time: float = 0
    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0

@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    model: str
    provider: str
    server_url: Optional[str] = None
    response_time: float = 0
    token_count: Optional[int] = None
    success: bool = True
    error: Optional[str] = None


class ServerPool:
    """
    Pool of Ollama servers that dispatches tasks to the first available server.
    
    When a server finishes a task, it becomes available immediately.
    The fastest server naturally handles more tasks because it returns faster.
    
    Usage:
        pool = ServerPool(servers)
        server = await pool.acquire()
        try:
            result = await llm_client.generate_on_server(messages, server)
        finally:
            pool.release(server)
    """
    
    def __init__(self, servers: List[OllamaServer]):
        self._servers = servers
        self._available = asyncio.Queue()
        self._initialized = False
        
    async def initialize(self):
        """Initialize the pool by adding all servers to the available queue"""
        if self._initialized:
            return
        # Add servers ordered by response_time (fastest first)
        # This way, when all servers are available, fastest gets picked first
        sorted_servers = sorted(self._servers, key=lambda s: s.response_time)
        for server in sorted_servers:
            if server.is_healthy:
                await self._available.put(server)
        self._initialized = True
        logger.info(f"Server pool initialized with {self._available.qsize()} servers")
    
    async def acquire(self) -> OllamaServer:
        """
        Acquire a server from the pool. Blocks until a server is available.
        The first server to become available is returned.
        """
        if not self._initialized:
            await self.initialize()
        server = await self._available.get()
        logger.debug(f"Acquired server: {server.url}")
        return server
    
    def release(self, server: OllamaServer):
        """Return a server to the pool, making it available for the next task"""
        self._available.put_nowait(server)
        logger.debug(f"Released server: {server.url}")
    
    def available_count(self) -> int:
        """Number of currently available servers"""
        return self._available.qsize()


class LLMClient:
    """Unified LLM client with load balancing and failover"""
    
    # Qwen3 models require special handling to suppress chain-of-thought
    QWEN3_MODELS = ['qwen3', 'qwen3:4b', 'qwen3:8b', 'qwen3:14b', 'qwen3:32b', 'qwen3:72b']
    
    # Qwen3-specific JSON enforcement (appended to original system prompt)
    QWEN3_JSON_SUFFIX = """

CRITICAL OUTPUT RULES FOR JSON:
- Output ONLY valid JSON, no explanation or chain-of-thought
- ALL 5 FIELDS ARE REQUIRED: source_category, source_label, relationship, target_category, target_label
- source_category and target_category MUST be exactly "Person" or "Company"

EXAMPLE OUTPUT:
{"relationships": [{"source_category": "Person", "source_label": "Alex Chen", "relationship": "ceo_of", "target_category": "Company", "target_label": "TechFlow"}]}"""
    
    def __init__(self):
        # Load configuration
        self.config_loader = get_config_loader()
        
        # Validate configuration
        errors = self.config_loader.validate_config()
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        self.provider = LLMProvider(self.config_loader.get('llm.provider', 'cloud'))
        self.openai_client = None
        self.ollama_servers: List[OllamaServer] = []
        self.current_server_index = 0
        self.load_balance_strategy = LoadBalanceStrategy(
            self.config_loader.get('llm.ollama.load_balance_strategy', 'round_robin')
        )
        self.health_check_task = None
        self._initialize()
    
    def _is_qwen3_model(self, model: str) -> bool:
        """Check if the model is a Qwen3 model that requires special handling"""
        model_lower = model.lower()
        return any(qwen in model_lower for qwen in ['qwen3', 'qwen-3'])
    
    def _initialize(self):
        """Initialize the LLM client based on configuration"""
        if self.provider == LLMProvider.CLOUD:
            self._initialize_openai()
        else:
            self._initialize_ollama()
    
    def _initialize_openai(self):
        """Initialize OpenAI client"""
        api_key = self.config_loader.get_openai_api_key()
        if not api_key:
            raise ValueError("OpenAI API key is required when LLM_PROVIDER=cloud")
        
        self.openai_client = openai.AsyncOpenAI(api_key=api_key)
        model = self.config_loader.get('llm.cloud.openai.model', 'gpt-4o-mini')
        logger.info(f"Initialized OpenAI client with model: {model}")
    
    def _initialize_ollama(self):
        """Initialize Ollama servers"""
        servers_config = self.config_loader.get('llm.ollama.servers', [])
        if not servers_config:
            raise ValueError("Ollama configuration is required when LLM_PROVIDER=ollama")
        
        enabled_servers = [s for s in servers_config if s.get('enabled', True)]
        if not enabled_servers:
            raise ValueError("At least one Ollama server must be enabled")
        
        self.ollama_servers = [OllamaServer(url=server['url']) for server in enabled_servers]
        server_names = [server['name'] for server in enabled_servers]
        logger.info(f"Initialized {len(self.ollama_servers)} Ollama servers: {server_names}")
        
        # Start health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def _health_check_loop(self):
        """Background health check for Ollama servers"""
        if self.provider != LLMProvider.OLLAMA:
            return
        
        interval = self.config_loader.get('llm.ollama.health_check.interval', 30)
        timeout = self.config_loader.get('llm.ollama.health_check.timeout', 10)
        
        while True:
            try:
                await asyncio.sleep(interval)
                await self._check_all_servers_health(timeout)
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    async def _check_all_servers_health(self, timeout: int):
        """Check health of all Ollama servers"""
        tasks = []
        for server in self.ollama_servers:
            task = asyncio.create_task(self._check_server_health(server, timeout))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_server_health(self, server: OllamaServer, timeout: int):
        """Check health of a single Ollama server"""
        try:
            start_time = time.time()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.get(f"{server.url}/api/tags") as response:
                    if response.status == 200:
                        server.is_healthy = True
                        server.response_time = time.time() - start_time
                        server.last_health_check = time.time()
                        logger.debug(f"Server {server.url} is healthy (response time: {server.response_time:.2f}s)")
                    else:
                        server.is_healthy = False
                        logger.warning(f"Server {server.url} returned status {response.status}")
        except Exception as e:
            server.is_healthy = False
            logger.warning(f"Server {server.url} health check failed: {e}")
    
    def _get_healthy_servers(self) -> List[OllamaServer]:
        """Get list of healthy Ollama servers"""
        return [server for server in self.ollama_servers if server.is_healthy]
    
    def create_server_pool(self) -> ServerPool:
        """
        Create a server pool for work-queue based processing.
        
        Use this when you want the fastest server to handle most tasks:
        - Tasks wait for an available server
        - Fast server finishes quickly, becomes available for next task
        - Naturally balances load based on actual server performance
        
        Returns:
            ServerPool instance for acquiring/releasing servers
        """
        healthy_servers = self._get_healthy_servers()
        if not healthy_servers:
            raise ValueError("No healthy Ollama servers available")
        return ServerPool(healthy_servers)
    
    async def generate_on_server(
        self, 
        messages: List[Dict[str, str]], 
        server: OllamaServer,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using a specific Ollama server.
        
        Use this with ServerPool.acquire() for work-queue based processing:
        
            pool = llm_client.create_server_pool()
            server = await pool.acquire()
            try:
                response = await llm_client.generate_on_server(messages, server)
            finally:
                pool.release(server)
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            server: The specific OllamaServer to use
            **kwargs: Additional parameters for generation
        
        Returns:
            LLMResponse with the result
        """
        server_name = server.url.replace("http://", "").replace(":11434", "")
        print(f"      📤 Dispatched to {server_name}")
        
        try:
            response = await self._try_ollama_server(server, messages, **kwargs)
            return response
        except Exception as e:
            logger.warning(f"Server {server.url} exception: {e}")
            server.failed_requests += 1
            return LLMResponse(
                content="",
                model=self.config_loader.get('llm.ollama.model', 'gemma3:12b'),
                provider="ollama",
                server_url=server.url,
                success=False,
                error=str(e)
            )
    
    def _select_server(self) -> Optional[OllamaServer]:
        """Select server based on load balancing strategy"""
        healthy_servers = self._get_healthy_servers()
        if not healthy_servers:
            return None
        
        if self.load_balance_strategy == LoadBalanceStrategy.ROUND_ROBIN:
            server = healthy_servers[self.current_server_index % len(healthy_servers)]
            self.current_server_index = (self.current_server_index + 1) % len(healthy_servers)
            return server
        
        elif self.load_balance_strategy == LoadBalanceStrategy.RANDOM:
            return random.choice(healthy_servers)
        
        elif self.load_balance_strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return min(healthy_servers, key=lambda s: s.active_connections)
        
        elif self.load_balance_strategy == LoadBalanceStrategy.FASTEST_RESPONSE:
            return min(healthy_servers, key=lambda s: s.response_time)
        
        return healthy_servers[0]
    
    async def generate(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Generate response using configured LLM provider"""
        if self.provider == LLMProvider.CLOUD:
            return await self._generate_openai(messages, **kwargs)
        else:
            return await self._generate_ollama(messages, **kwargs)
    
    async def _generate_openai(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Generate response using OpenAI"""
        try:
            start_time = time.time()
            model = self.config_loader.get('llm.cloud.openai.model', 'gpt-4o-mini')
            timeout = self.config_loader.get('llm.cloud.openai.timeout', 60)
            
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=kwargs.get("temperature", 0.1),
                max_tokens=kwargs.get("max_tokens", 2000),
                timeout=timeout
            )
            
            response_time = time.time() - start_time
            content = response.choices[0].message.content
            token_count = response.usage.total_tokens if response.usage else None
            
            return LLMResponse(
                content=content,
                model=model,
                provider="openai",
                response_time=response_time,
                token_count=token_count
            )
            
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return LLMResponse(
                content="",
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                provider="openai",
                success=False,
                error=str(e)
            )
    
    async def _generate_ollama(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Generate response using Ollama with failover"""
        if self.provider != LLMProvider.OLLAMA:
            return LLMResponse(
                content="",
                model="unknown",
                provider="ollama",
                success=False,
                error="Ollama configuration not available"
            )
        
        max_retries = self.config_loader.get('llm.ollama.max_retries', 3)
        retry_delay = self.config_loader.get('llm.ollama.retry_delay', 5)
        
        for attempt in range(max_retries):
            server = self._select_server()
            if not server:
                error_msg = "No healthy Ollama servers available"
                logger.error(error_msg)
                return LLMResponse(
                    content="",
                    model=os.getenv("OLLAMA_MODEL", "gemma3:12b"),
                    provider="ollama",
                    success=False,
                    error=error_msg
                )
            
            # Log which server is receiving this request
            server_name = server.url.replace("http://", "").replace(":11434", "")
            print(f"      📤 Dispatched to {server_name}")
            
            try:
                response = await self._try_ollama_server(server, messages, **kwargs)
                if response.success:
                    return response
                else:
                    logger.warning(f"Server {server.url} failed: {response.error}")
                    server.failed_requests += 1
                    
            except Exception as e:
                logger.warning(f"Server {server.url} exception: {e}")
                server.failed_requests += 1
            
            # Wait before retry
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
        
        # All retries failed
        return LLMResponse(
            content="",
            model=os.getenv("OLLAMA_MODEL", "gemma3:12b"),
            provider="ollama",
            success=False,
            error="All Ollama servers failed after retries"
        )
    
    async def _try_ollama_server(self, server: OllamaServer, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Try to generate response from a specific Ollama server"""
        try:
            start_time = time.time()
            server.active_connections += 1
            server.total_requests += 1
            
            model = self.config_loader.get('llm.ollama.model', 'gemma3:12b')
            timeout = self.config_loader.get('llm.ollama.timeout', 60)
            
            # Check if this is a Qwen3 model - use chat API with special handling
            if self._is_qwen3_model(model):
                return await self._try_ollama_server_qwen3(server, messages, model, timeout, **kwargs)
            
            # Standard Ollama handling for non-Qwen3 models
            combined_prompt = self._combine_messages(messages)
            
            payload = {
                "model": model,
                "prompt": combined_prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.1),
                    "num_predict": kwargs.get("max_tokens", 2000)
                }
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(f"{server.url}/api/generate", json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("response", "")
                        response_time = time.time() - start_time
                        server.response_time = response_time
                        
                        return LLMResponse(
                            content=content,
                            model=model,
                            provider="ollama",
                            server_url=server.url,
                            response_time=response_time
                        )
                    else:
                        error_msg = f"HTTP {response.status}: {await response.text()}"
                        return LLMResponse(
                            content="",
                            model=model,
                            provider="ollama",
                            server_url=server.url,
                            success=False,
                            error=error_msg
                        )
        
        except asyncio.TimeoutError:
            server_name = server.url.replace("http://", "").replace(":11434", "")
            error_msg = f"[{server_name}] Request timed out - server may be overloaded"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=os.getenv("OLLAMA_MODEL", "gemma3:12b"),
                provider="ollama",
                server_url=server.url,
                success=False,
                error=error_msg
            )
        except aiohttp.ClientConnectorError as e:
            server_name = server.url.replace("http://", "").replace(":11434", "")
            error_msg = f"[{server_name}] Connection failed: {e.os_error if hasattr(e, 'os_error') else e}"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=os.getenv("OLLAMA_MODEL", "gemma3:12b"),
                provider="ollama",
                server_url=server.url,
                success=False,
                error=error_msg
            )
        except Exception as e:
            server_name = server.url.replace("http://", "").replace(":11434", "")
            error_type = type(e).__name__
            error_msg = f"[{server_name}] {error_type}: {str(e) or 'No error details'}"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=os.getenv("OLLAMA_MODEL", "gemma3:12b"),
                provider="ollama",
                server_url=server.url,
                success=False,
                error=error_msg
            )
        finally:
            server.active_connections = max(0, server.active_connections - 1)
    
    async def _try_ollama_server_qwen3(self, server: OllamaServer, messages: List[Dict[str, str]], 
                                        model: str, timeout: int, **kwargs) -> LLMResponse:
        """
        Special handling for Qwen3 models using chat API with JSON format.
        Qwen3 models require specific prompting to suppress chain-of-thought reasoning.
        """
        try:
            start_time = time.time()
            
            # Build messages for Qwen3 - use original system prompt + JSON enforcement
            qwen_messages = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    # Append Qwen3 JSON enforcement to the original system prompt
                    qwen_messages.append({
                        "role": "system",
                        "content": content + self.QWEN3_JSON_SUFFIX
                    })
                elif role == "user":
                    qwen_messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    qwen_messages.append({"role": role, "content": content})
            
            # Note: format:json works well for qwen3:8b but causes issues with qwen3:14b
            # For 14b models, we skip format:json and parse the response manually
            use_json_format = "14b" not in model.lower() and "32b" not in model.lower() and "72b" not in model.lower()
            
            payload = {
                "model": model,
                "messages": qwen_messages,
                "stream": False,
                "options": {
                    "temperature": 0,  # Deterministic for structured output
                    "top_p": 1,
                    "num_predict": kwargs.get("max_tokens", 4000),
                    "num_ctx": 8192
                }
            }
            
            if use_json_format:
                payload["format"] = "json"  # Force JSON output - works for smaller Qwen3 models
            
            # Extract server name for logging
            server_name = server.url.replace("http://", "").replace(":11434", "")
            logger.info(f"[{server_name}] Qwen3 request: model={model}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                async with session.post(f"{server.url}/api/chat", json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("message", {}).get("content", "")
                        response_time = time.time() - start_time
                        server.response_time = response_time
                        
                        # Handle Qwen3 thinking models (14b, 32b, 72b) - extract JSON after </think>
                        if "</think>" in content:
                            content = content.split("</think>")[-1].strip()
                        
                        # Also try to extract JSON if response contains other text
                        if content and not content.startswith("{"):
                            # Find the JSON object
                            json_start = content.find("{")
                            json_end = content.rfind("}") + 1
                            if json_start != -1 and json_end > json_start:
                                content = content[json_start:json_end]
                        
                        logger.info(f"[{server_name}] Qwen3 response: {len(content)} chars in {response_time:.2f}s")
                        
                        return LLMResponse(
                            content=content,
                            model=model,
                            provider="ollama",
                            server_url=server.url,
                            response_time=response_time,
                            token_count=data.get("eval_count")
                        )
                    else:
                        error_msg = f"HTTP {response.status}: {await response.text()}"
                        return LLMResponse(
                            content="",
                            model=model,
                            provider="ollama",
                            server_url=server.url,
                            success=False,
                            error=error_msg
                        )
        
        except asyncio.TimeoutError:
            server_name = server.url.replace("http://", "").replace(":11434", "")
            error_msg = f"[{server_name}] Request timed out after {timeout}s - server may be overloaded or model too slow"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=model,
                provider="ollama",
                server_url=server.url,
                success=False,
                error=error_msg
            )
        except aiohttp.ClientConnectorError as e:
            server_name = server.url.replace("http://", "").replace(":11434", "")
            error_msg = f"[{server_name}] Connection failed: {e.os_error if hasattr(e, 'os_error') else e}"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=model,
                provider="ollama",
                server_url=server.url,
                success=False,
                error=error_msg
            )
        except aiohttp.ServerDisconnectedError:
            server_name = server.url.replace("http://", "").replace(":11434", "")
            error_msg = f"[{server_name}] Server disconnected - may have crashed or restarted"
            logger.error(error_msg)
            return LLMResponse(
                content="",
                model=model,
                provider="ollama",
                server_url=server.url,
                success=False,
                error=error_msg
            )
        except Exception as e:
            server_name = server.url.replace("http://", "").replace(":11434", "")
            error_type = type(e).__name__
            error_msg = f"[{server_name}] {error_type}: {str(e) or 'No error details'}"
            logger.error(f"[{server_name}] Qwen3 request failed: {error_msg}")
            return LLMResponse(
                content="",
                model=model,
                provider="ollama",
                server_url=server.url,
                success=False,
                error=error_msg
            )
    
    def _combine_messages(self, messages: List[Dict[str, str]]) -> str:
        """Combine system and user messages for Ollama"""
        combined = []
        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")
            if role == "system":
                combined.append(f"System: {content}")
            elif role == "user":
                combined.append(f"User: {content}")
            elif role == "assistant":
                combined.append(f"Assistant: {content}")
        
        return "\n\n".join(combined)
    
    async def get_server_status(self) -> Dict[str, Any]:
        """Get status of all configured servers"""
        if self.provider == LLMProvider.CLOUD:
            return {
                "provider": "openai",
                "status": "healthy" if self.openai_client else "unavailable",
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini")
            }
        else:
            healthy_servers = self._get_healthy_servers()
            return {
                "provider": "ollama",
                "total_servers": len(self.ollama_servers),
                "healthy_servers": len(healthy_servers),
                "load_balance_strategy": self.load_balance_strategy.value,
                "servers": [
                    {
                        "url": server.url,
                        "healthy": server.is_healthy,
                        "response_time": server.response_time,
                        "active_connections": server.active_connections,
                        "total_requests": server.total_requests,
                        "failed_requests": server.failed_requests,
                        "last_health_check": server.last_health_check
                    }
                    for server in self.ollama_servers
                ]
            }
    
    async def close(self):
        """Clean up resources"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

# Global LLM client instance
_llm_client = None

async def get_llm_client() -> LLMClient:
    """Get the global LLM client instance"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client

async def close_llm_client():
    """Close the global LLM client"""
    global _llm_client
    if _llm_client:
        await _llm_client.close()
        _llm_client = None
