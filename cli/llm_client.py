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
from llm_config_loader import get_config_loader, LLMConfig

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

class LLMClient:
    """Unified LLM client with load balancing and failover"""
    
    def __init__(self):
        # Load configuration
        self.config_loader = get_config_loader()
        self.config = self.config_loader.get_config()
        
        # Validate configuration
        errors = self.config_loader.validate_config()
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        self.provider = LLMProvider(self.config.provider)
        self.openai_client = None
        self.ollama_servers: List[OllamaServer] = []
        self.current_server_index = 0
        self.load_balance_strategy = LoadBalanceStrategy(
            self.config.ollama.load_balance_strategy if self.config.ollama else "round_robin"
        )
        self.health_check_task = None
        self._initialize()
    
    def _initialize(self):
        """Initialize the LLM client based on configuration"""
        if self.provider == LLMProvider.CLOUD:
            self._initialize_openai()
        else:
            self._initialize_ollama()
    
    def _initialize_openai(self):
        """Initialize OpenAI client"""
        if not self.config.cloud or not self.config.cloud.openai_api_key:
            raise ValueError("OpenAI API key is required when LLM_PROVIDER=cloud")
        
        self.openai_client = openai.AsyncOpenAI(api_key=self.config.cloud.openai_api_key)
        logger.info(f"Initialized OpenAI client with model: {self.config.cloud.openai_model}")
    
    def _initialize_ollama(self):
        """Initialize Ollama servers"""
        if not self.config.ollama:
            raise ValueError("Ollama configuration is required when LLM_PROVIDER=ollama")
        
        enabled_servers = self.config_loader.get_enabled_ollama_servers()
        if not enabled_servers:
            raise ValueError("At least one Ollama server must be enabled")
        
        self.ollama_servers = [OllamaServer(url=server.url) for server in enabled_servers]
        server_names = [server.name for server in enabled_servers]
        logger.info(f"Initialized {len(self.ollama_servers)} Ollama servers: {server_names}")
        
        # Start health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())
    
    async def _health_check_loop(self):
        """Background health check for Ollama servers"""
        if not self.config.ollama:
            return
        
        interval = self.config.ollama.health_check_interval
        timeout = self.config.ollama.health_check_timeout
        
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
            model = self.config.cloud.openai_model
            timeout = self.config.cloud.openai_timeout
            
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
        if not self.config.ollama:
            return LLMResponse(
                content="",
                model="unknown",
                provider="ollama",
                success=False,
                error="Ollama configuration not available"
            )
        
        max_retries = self.config.ollama.max_retries
        retry_delay = self.config.ollama.retry_delay
        
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
            
            # Combine system and user messages for Ollama
            combined_prompt = self._combine_messages(messages)
            model = self.config.ollama.model
            timeout = self.config.ollama.timeout
            
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
        
        except Exception as e:
            return LLMResponse(
                content="",
                model=os.getenv("OLLAMA_MODEL", "gemma3:12b"),
                provider="ollama",
                server_url=server.url,
                success=False,
                error=str(e)
            )
        finally:
            server.active_connections = max(0, server.active_connections - 1)
    
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
