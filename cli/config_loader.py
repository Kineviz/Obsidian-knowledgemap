#!/usr/bin/env python3
"""
Unified Configuration Loader
Loads configuration from config.yaml and .env files
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

class ConfigLoader:
    """Loads configuration from config.yaml and .env files"""
    
    def __init__(self, config_path: str = None, env_path: str = None):
        # Default to parent directory for config files
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.yaml"
        if env_path is None:
            env_path = Path(__file__).parent.parent / ".env"
        self.config_path = Path(config_path)
        self.env_path = Path(env_path)
        self.config_data = {}
        self.env_data = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from both files"""
        # Load .env file
        if self.env_path.exists():
            load_dotenv(self.env_path)
            self.env_data = dict(os.environ)
        else:
            print(f"Warning: {self.env_path} not found, using environment variables only")
            self.env_data = dict(os.environ)
        
        # Load config.yaml
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = yaml.safe_load(f) or {}
        else:
            print(f"Warning: {self.config_path} not found, using defaults")
            self.config_data = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with environment variable override support"""
        # Check for environment variable override first
        env_key = key.upper().replace('.', '_')
        if env_key in self.env_data:
            return self.env_data[env_key]
        
        # Navigate through nested config
        keys = key.split('.')
        value = self.config_data
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_vault_path(self) -> Optional[str]:
        """Get vault path with environment variable override"""
        return self.get('vault.path') or os.getenv('VAULT_PATH')
    
    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from environment"""
        return os.getenv('OPENAI_API_KEY')
    
    def get_gemini_api_key(self) -> Optional[str]:
        """Get Gemini API key from environment"""
        return os.getenv('GEMINI_API_KEY')
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration with API key injection"""
        llm_config = self.get('llm', {})
        
        # Inject API key if using cloud provider
        if llm_config.get('provider') == 'cloud':
            api_key = self.get_openai_api_key()
            if api_key:
                if 'cloud' not in llm_config:
                    llm_config['cloud'] = {}
                if 'openai' not in llm_config['cloud']:
                    llm_config['cloud']['openai'] = {}
                llm_config['cloud']['openai']['api_key'] = api_key
            else:
                print("Warning: OPENAI_API_KEY not found in environment")
        
        return llm_config
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.get('database', {})
    
    def get_processing_config(self) -> Dict[str, Any]:
        """Get processing configuration"""
        return self.get('processing', {})
    
    def get_server_config(self) -> Dict[str, Any]:
        """Get server configuration"""
        return self.get('server', {})
    
    def validate_config(self) -> list:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Check required settings
        if not self.get_vault_path():
            errors.append("Vault path not configured (set vault.path in config.yaml or VAULT_PATH env var)")
        
        if self.get('llm.provider') == 'cloud' and not self.get_openai_api_key():
            errors.append("OpenAI API key not found (set OPENAI_API_KEY in .env)")
        
        if self.get('llm.provider') == 'gemini' and not self.get_gemini_api_key():
            errors.append("Gemini API key not found (set GEMINI_API_KEY in .env)")
        
        return errors
    
    def print_config_summary(self):
        """Print a summary of the current configuration"""
        print("Configuration Summary:")
        print(f"  Vault Path: {self.get_vault_path()}")
        print(f"  LLM Provider: {self.get('llm.provider', 'not set')}")
        print(f"  Database Port: {self.get('database.port', 'not set')}")
        print(f"  Server Port: {self.get('server.port', 'not set')}")
        print(f"  OpenAI API Key: {'Set' if self.get_openai_api_key() else 'Not set'}")
        print(f"  Gemini API Key: {'Set' if self.get_gemini_api_key() else 'Not set'}")

# Global config loader instance
_config_loader: Optional[ConfigLoader] = None

def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader

def reload_config():
    """Reload configuration from files"""
    global _config_loader
    _config_loader = None
    return get_config_loader()

if __name__ == "__main__":
    # Test the config loader
    loader = get_config_loader()
    loader.print_config_summary()
    
    errors = loader.validate_config()
    if errors:
        print("\nConfiguration Errors:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("\nConfiguration is valid!")
