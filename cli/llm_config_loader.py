#!/usr/bin/env python3
"""
LLM Configuration Loader
Loads configuration from YAML file and environment variables with fallbacks
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class OllamaServerConfig:
    """Configuration for a single Ollama server"""
    name: str
    url: str
    enabled: bool = True
    priority: int = 1

@dataclass
class CloudConfig:
    """Cloud provider configuration"""
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_timeout: int = 60

@dataclass
class OllamaConfig:
    """Ollama configuration"""
    servers: List[OllamaServerConfig]
    model: str = "gemma3:12b"
    timeout: int = 60
    max_retries: int = 3
    retry_delay: int = 5
    load_balance_strategy: str = "round_robin"
    health_check_interval: int = 30
    health_check_timeout: int = 10
    server_timeout: int = 300

@dataclass
class GlobalConfig:
    """Global configuration settings"""
    max_concurrent: int = 5
    chunk_threshold: float = 0.75
    chunk_size: int = 1024
    embedding_model: str = "minishlab/potion-base-8M"

@dataclass
class LLMConfig:
    """Complete LLM configuration"""
    provider: str
    cloud: Optional[CloudConfig] = None
    ollama: Optional[OllamaConfig] = None
    global_settings: Optional[GlobalConfig] = None

class LLMConfigLoader:
    """Loads and manages LLM configuration"""
    
    def __init__(self, config_file: str = "llm_config.yaml"):
        # Look for config file in root directory (same level as .env)
        self.config_file = Path(config_file)
        if not self.config_file.exists():
            # Try in parent directory if not found in current directory
            self.config_file = Path("..") / config_file
        self.config = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from YAML file and environment variables"""
        # Start with defaults
        config_data = {
            "provider": "cloud",
            "cloud": {
                "openai": {
                    "api_key": "",
                    "model": "gpt-4o-mini",
                    "timeout": 60
                }
            },
            "ollama": {
                "servers": [],
                "model": "gemma3:12b",
                "timeout": 60,
                "max_retries": 3,
                "retry_delay": 5,
                "load_balance_strategy": "round_robin",
                "health_check": {
                    "interval": 30,
                    "timeout": 10,
                    "server_timeout": 300
                }
            },
            "global": {
                "max_concurrent": 5,
                "chunk_threshold": 0.75,
                "chunk_size": 1024,
                "embedding_model": "minishlab/potion-base-8M"
            }
        }
        
        # Load from YAML file if it exists
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    yaml_config = yaml.safe_load(f)
                    if yaml_config:
                        config_data = self._merge_configs(config_data, yaml_config)
            except Exception as e:
                print(f"Warning: Could not load {self.config_file}: {e}")
        
        # Override with environment variables
        config_data = self._apply_env_overrides(config_data)
        
        # Parse into structured config
        self.config = self._parse_config(config_data)
    
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge configuration dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result
    
    def _apply_env_overrides(self, config: Dict) -> Dict:
        """Apply environment variable overrides"""
        # Provider selection
        if os.getenv("LLM_PROVIDER"):
            config["provider"] = os.getenv("LLM_PROVIDER")
        
        # Cloud configuration
        if os.getenv("OPENAI_API_KEY"):
            config["cloud"]["openai"]["api_key"] = os.getenv("OPENAI_API_KEY")
        if os.getenv("OPENAI_MODEL"):
            config["cloud"]["openai"]["model"] = os.getenv("OPENAI_MODEL")
        if os.getenv("OPENAI_TIMEOUT"):
            config["cloud"]["openai"]["timeout"] = int(os.getenv("OPENAI_TIMEOUT"))
        
        # Ollama configuration
        if os.getenv("OLLAMA_SERVERS"):
            # Parse comma-separated servers (backward compatibility)
            server_urls = [url.strip() for url in os.getenv("OLLAMA_SERVERS").split(",") if url.strip()]
            config["ollama"]["servers"] = [
                {"name": f"server_{i+1}", "url": url, "enabled": True, "priority": i+1}
                for i, url in enumerate(server_urls)
            ]
        
        if os.getenv("OLLAMA_MODEL"):
            config["ollama"]["model"] = os.getenv("OLLAMA_MODEL")
        if os.getenv("OLLAMA_TIMEOUT"):
            config["ollama"]["timeout"] = int(os.getenv("OLLAMA_TIMEOUT"))
        if os.getenv("OLLAMA_MAX_RETRIES"):
            config["ollama"]["max_retries"] = int(os.getenv("OLLAMA_MAX_RETRIES"))
        if os.getenv("OLLAMA_RETRY_DELAY"):
            config["ollama"]["retry_delay"] = int(os.getenv("OLLAMA_RETRY_DELAY"))
        if os.getenv("OLLAMA_LOAD_BALANCE_STRATEGY"):
            config["ollama"]["load_balance_strategy"] = os.getenv("OLLAMA_LOAD_BALANCE_STRATEGY")
        
        # Health check configuration
        if os.getenv("OLLAMA_HEALTH_CHECK_INTERVAL"):
            config["ollama"]["health_check"]["interval"] = int(os.getenv("OLLAMA_HEALTH_CHECK_INTERVAL"))
        if os.getenv("OLLAMA_HEALTH_CHECK_TIMEOUT"):
            config["ollama"]["health_check"]["timeout"] = int(os.getenv("OLLAMA_HEALTH_CHECK_TIMEOUT"))
        if os.getenv("OLLAMA_SERVER_TIMEOUT"):
            config["ollama"]["health_check"]["server_timeout"] = int(os.getenv("OLLAMA_SERVER_TIMEOUT"))
        
        # Global settings
        if os.getenv("MAX_CONCURRENT"):
            config["global"]["max_concurrent"] = int(os.getenv("MAX_CONCURRENT"))
        if os.getenv("CHUNK_THRESHOLD"):
            config["global"]["chunk_threshold"] = float(os.getenv("CHUNK_THRESHOLD"))
        if os.getenv("CHUNK_SIZE"):
            config["global"]["chunk_size"] = int(os.getenv("CHUNK_SIZE"))
        if os.getenv("EMBEDDING_MODEL"):
            config["global"]["embedding_model"] = os.getenv("EMBEDDING_MODEL")
        
        return config
    
    def _parse_config(self, config_data: Dict) -> LLMConfig:
        """Parse configuration data into structured objects"""
        # Parse cloud configuration
        cloud_config = None
        if config_data.get("cloud") and config_data["cloud"].get("openai"):
            openai_config = config_data["cloud"]["openai"]
            cloud_config = CloudConfig(
                openai_api_key=openai_config.get("api_key", ""),
                openai_model=openai_config.get("model", "gpt-4o-mini"),
                openai_timeout=openai_config.get("timeout", 60)
            )
        
        # Parse Ollama configuration
        ollama_config = None
        if config_data.get("ollama"):
            ollama_data = config_data["ollama"]
            servers = []
            for server_data in ollama_data.get("servers", []):
                servers.append(OllamaServerConfig(
                    name=server_data.get("name", "unnamed"),
                    url=server_data.get("url", ""),
                    enabled=server_data.get("enabled", True),
                    priority=server_data.get("priority", 1)
                ))
            
            health_check = ollama_data.get("health_check", {})
            ollama_config = OllamaConfig(
                servers=servers,
                model=ollama_data.get("model", "gemma3:12b"),
                timeout=ollama_data.get("timeout", 60),
                max_retries=ollama_data.get("max_retries", 3),
                retry_delay=ollama_data.get("retry_delay", 5),
                load_balance_strategy=ollama_data.get("load_balance_strategy", "round_robin"),
                health_check_interval=health_check.get("interval", 30),
                health_check_timeout=health_check.get("timeout", 10),
                server_timeout=health_check.get("server_timeout", 300)
            )
        
        # Parse global configuration
        global_config = None
        if config_data.get("global"):
            global_data = config_data["global"]
            global_config = GlobalConfig(
                max_concurrent=global_data.get("max_concurrent", 5),
                chunk_threshold=global_data.get("chunk_threshold", 0.75),
                chunk_size=global_data.get("chunk_size", 1024),
                embedding_model=global_data.get("embedding_model", "minishlab/potion-base-8M")
            )
        
        return LLMConfig(
            provider=config_data.get("provider", "cloud"),
            cloud=cloud_config,
            ollama=ollama_config,
            global_settings=global_config
        )
    
    def get_config(self) -> LLMConfig:
        """Get the current configuration"""
        return self.config
    
    def get_enabled_ollama_servers(self) -> List[OllamaServerConfig]:
        """Get list of enabled Ollama servers sorted by priority"""
        if not self.config or not self.config.ollama:
            return []
        
        enabled_servers = [s for s in self.config.ollama.servers if s.enabled]
        return sorted(enabled_servers, key=lambda s: s.priority)
    
    def get_ollama_server_urls(self) -> List[str]:
        """Get list of enabled Ollama server URLs (for backward compatibility)"""
        enabled_servers = self.get_enabled_ollama_servers()
        return [server.url for server in enabled_servers]
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if not self.config:
            errors.append("Configuration not loaded")
            return errors
        
        if self.config.provider == "cloud":
            if not self.config.cloud or not self.config.cloud.openai_api_key:
                errors.append("OpenAI API key required for cloud provider")
        
        elif self.config.provider == "ollama":
            if not self.config.ollama:
                errors.append("Ollama configuration required for ollama provider")
            else:
                enabled_servers = self.get_enabled_ollama_servers()
                if not enabled_servers:
                    errors.append("At least one Ollama server must be enabled")
        
        return errors
    
    def save_config(self, config: LLMConfig = None):
        """Save configuration to YAML file"""
        if config is None:
            config = self.config
        
        if not config:
            return
        
        # Convert config to dictionary
        config_dict = {
            "provider": config.provider,
            "global": {
                "max_concurrent": config.global_settings.max_concurrent if config.global_settings else 5,
                "chunk_threshold": config.global_settings.chunk_threshold if config.global_settings else 0.75,
                "chunk_size": config.global_settings.chunk_size if config.global_settings else 1024,
                "embedding_model": config.global_settings.embedding_model if config.global_settings else "minishlab/potion-base-8M"
            }
        }
        
        if config.cloud:
            config_dict["cloud"] = {
                "openai": {
                    "api_key": config.cloud.openai_api_key,
                    "model": config.cloud.openai_model,
                    "timeout": config.cloud.openai_timeout
                }
            }
        
        if config.ollama:
            config_dict["ollama"] = {
                "servers": [
                    {
                        "name": server.name,
                        "url": server.url,
                        "enabled": server.enabled,
                        "priority": server.priority
                    }
                    for server in config.ollama.servers
                ],
                "model": config.ollama.model,
                "timeout": config.ollama.timeout,
                "max_retries": config.ollama.max_retries,
                "retry_delay": config.ollama.retry_delay,
                "load_balance_strategy": config.ollama.load_balance_strategy,
                "health_check": {
                    "interval": config.ollama.health_check_interval,
                    "timeout": config.ollama.health_check_timeout,
                    "server_timeout": config.ollama.server_timeout
                }
            }
        
        # Save to file
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

# Global config loader instance
_config_loader = None

def get_config_loader() -> LLMConfigLoader:
    """Get the global configuration loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = LLMConfigLoader()
    return _config_loader
